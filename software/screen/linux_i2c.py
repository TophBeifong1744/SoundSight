"""Linux PS I2C0 owner and native I2C_RDWR ABI. No PS register access."""
import ctypes
import os
from pathlib import Path
import re
import stat

DT_ROOT = Path('/sys/firmware/devicetree/base')
TARGET = '/amba/i2c@e0004000'
ADDRESSES = (0x14, 0x38, 0x5d)
I2C_FUNCS, I2C_RDWR, I2C_FUNC_I2C, I2C_M_RD = 0x0705, 0x0707, 1, 1


class I2CMessage(ctypes.Structure):
    # 使用本机自然对齐，不把 ARM32/ARM64 指针结构写成 packed 字节串。
    _fields_ = [('addr', ctypes.c_uint16), ('flags', ctypes.c_uint16),
                ('len', ctypes.c_uint16), ('buf', ctypes.POINTER(ctypes.c_uint8))]


class I2CTransfer(ctypes.Structure):
    _fields_ = [('msgs', ctypes.POINTER(I2CMessage)), ('nmsgs', ctypes.c_uint32)]


def abi_details():
    pointer = ctypes.sizeof(ctypes.c_void_p)
    expected = {4: (12, 8), 8: (16, 16)}
    sizes = (ctypes.sizeof(I2CMessage), ctypes.sizeof(I2CTransfer))
    if pointer not in expected or sizes != expected[pointer] or I2CMessage.buf.offset != 8:
        raise RuntimeError('Unsupported native Linux I2C ABI')
    return dict(pointer_bytes=pointer, msg_bytes=sizes[0], transfer_bytes=sizes[1], buf_offset=8)


def read_property(node, name, default=b''):
    path = node/name
    return path.read_bytes() if path.is_file() else default


def strings(value):
    return value.rstrip(b'\0').decode('ascii').split('\0') if value else []


def cells(value):
    if len(value) % 4:
        raise ValueError('Unaligned device-tree cells')
    return [int.from_bytes(value[i:i+4], 'big') for i in range(0, len(value), 4)]


def node_details(dt_root=DT_ROOT):
    # 路径来自本板只读回传，仍核对每个运行时属性，绝不猜总线编号或 phandle。
    node = dt_root/TARGET.lstrip('/')
    if not node.is_dir():
        raise RuntimeError('PS_I2C_DT_NODE_MISSING: '+str(node))
    props = {name: read_property(node, name) for name in
             ('reg', 'compatible', 'status', 'clocks', 'interrupts', 'clock-frequency', 'resets')}
    result = dict(target_path=TARGET, node=str(node.resolve()),
                  compatible=strings(props['compatible']), status=(strings(props['status']) or ['okay'])[0],
                  reg=cells(props['reg']), clocks=cells(props['clocks']),
                  interrupts=cells(props['interrupts']), clock_frequency=cells(props['clock-frequency']),
                  resets=cells(props['resets']))
    if result['reg'] != [0xe0004000, 0x1000] or 'cdns,i2c-r1p10' not in result['compatible']:
        raise RuntimeError('PS_I2C_DT_IDENTITY_MISMATCH: '+str(result))
    if cells(read_property(node.parent, '#address-cells')) != [1] or cells(read_property(node.parent, '#size-cells')) != [1]:
        raise RuntimeError('PS_I2C_DT_PARENT_CELLS_UNCONFIRMED')
    if len(result['clocks']) != 2 or result['clocks'][1] != 38 or result['interrupts'] != [0, 25, 4]:
        raise RuntimeError('PS_I2C_DT_CLOCK_IRQ_UNCONFIRMED: '+str(result))
    providers = [p.parent for p in dt_root.rglob('phandle') if cells(p.read_bytes()) == result['clocks'][:1]]
    if len(providers) != 1 or 'xlnx,ps7-clkc' not in strings(read_property(providers[0], 'compatible')):
        raise RuntimeError('PS_I2C_CLOCK_PROVIDER_UNCONFIRMED')
    # 不覆盖既有 MIO pinctrl 或内核触摸设备；专用 EMIO 控制器必须没有子设备。
    if any(p.name.startswith('pinctrl-') for p in node.iterdir()):
        raise RuntimeError('PS_I2C_PINCTRL_PRESENT: inspect before using EMIO')
    children = [p.name for p in node.iterdir() if p.is_dir() and (p/'reg').is_file()]
    if children:
        raise RuntimeError('PS_I2C_DT_CLIENTS_PRESENT: '+str(children))
    return result


def clients_on_bus(number, sys_root=Path('/sys')):
    pattern = re.compile(re.escape(str(number)) + r'-[0-9a-fA-F]{4}$')
    return sorted(p.name for p in (sys_root/'bus/i2c/devices').glob('*') if pattern.fullmatch(p.name))


def find_adapter(dt_root=DT_ROOT, sys_root=Path('/sys'), dev_root=Path('/dev')):
    details = node_details(dt_root)
    if details['status'] not in ('okay', 'ok') or details['clock_frequency'] != [100000]:
        raise RuntimeError('PS_I2C_NOT_READY: require enabled 100000 Hz; run screen-i2c check/apply')
    target = Path(details['node'])
    platforms = [p for p in (sys_root/'bus/platform/devices').glob('*')
                 if (p/'of_node').exists() and (p/'of_node').resolve() == target]
    if len(platforms) != 1:
        raise RuntimeError('PS_I2C_PLATFORM_NOT_BOUND: '+str([str(p) for p in platforms]))
    platform = platforms[0]
    if not (platform/'driver').exists() or (platform/'driver').resolve().name not in ('cdns-i2c', 'i2c-cadence'):
        raise RuntimeError('PS_I2C_CADENCE_DRIVER_MISSING: '+str(platform))
    adapters = []
    for adapter in (sys_root/'class/i2c-adapter').glob('i2c-*'):
        if not re.fullmatch(r'i2c-\d+', adapter.name):
            continue
        # sysfs 的 adapter 目录应属于该平台设备；同时校验 of_node（若导出）。
        resolved = adapter.resolve()
        if platform.resolve() not in resolved.parents:
            continue
        for link in (adapter/'of_node', adapter/'device/of_node'):
            if link.exists() and link.resolve() != target:
                raise RuntimeError('PS_I2C_ADAPTER_OF_NODE_MISMATCH')
        adapters.append(adapter)
    if len(adapters) != 1:
        raise RuntimeError('PS_I2C_ADAPTER_AMBIGUOUS_OR_MISSING')
    number = int(adapters[0].name.split('-')[1])
    clients = clients_on_bus(number, sys_root)
    if clients:
        raise RuntimeError('PS_I2C_BUS_HAS_CLIENTS: '+str(clients))
    device = dev_root/('i2c-%d' % number)
    if not device.exists():
        raise RuntimeError('PS_I2C_DEV_MISSING: '+str(device)+'; i2c-dev must already be available')
    details.update(bus=number, device=str(device), adapter=str(adapters[0].resolve()), platform=str(platform.resolve()),
                   driver=(platform/'driver').resolve().name)
    return details


class LinuxI2C:
    def __init__(self, dt_root=DT_ROOT, sys_root=Path('/sys'), dev_root=Path('/dev')):
        self.fd, self.owner = None, None
        self.sys_root = sys_root
        self.dt_root, self.dev_root = dt_root, dev_root
        self.abi = abi_details()
        import fcntl
        try:
            self.owner = open('/tmp/soundsight-ps-i2c0-owner.lock', 'a')
            fcntl.flock(self.owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.details = find_adapter(dt_root, sys_root, dev_root)
            self.fd = os.open(self.details['device'], os.O_RDWR | os.O_CLOEXEC)
            opened = os.fstat(self.fd)
            if not stat.S_ISCHR(opened.st_mode) or os.major(opened.st_rdev) != 89 or os.minor(opened.st_rdev) != self.details['bus']:
                raise RuntimeError('PS_I2C_DEV_IDENTITY_MISMATCH')
            self.libc = ctypes.CDLL(None, use_errno=True)
            self.libc.ioctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_void_p]
            self.libc.ioctl.restype = ctypes.c_int
            functions = ctypes.c_ulong()
            self._ioctl(I2C_FUNCS, ctypes.byref(functions))
            if not functions.value & I2C_FUNC_I2C:
                raise RuntimeError('PS_I2C_COMBINED_TRANSFER_UNSUPPORTED')
            self._ownership()
        except BaseException:
            self.close()
            raise

    def _ownership(self):
        # 地址占用不能靠 I2C_RDWR 自动发现；每次传输前检查整个专用总线。
        clients = clients_on_bus(self.details['bus'], self.sys_root)
        adapter = self.sys_root/('class/i2c-adapter/i2c-%d' % self.details['bus'])
        platform = Path(self.details['platform'])
        node = self.dt_root/TARGET.lstrip('/')
        if (clients or not adapter.exists() or str(adapter.resolve()) != self.details['adapter']
                or not (platform/'of_node').exists() or (platform/'of_node').resolve() != node.resolve()
                or not (platform/'driver').exists() or (platform/'driver').resolve().name != self.details['driver']
                or (strings(read_property(node, 'status')) or ['okay'])[0] not in ('okay', 'ok')
                or cells(read_property(node, 'clock-frequency')) != [100000]):
            raise RuntimeError('PS_I2C_OWNERSHIP_CHANGED')

    def _ioctl(self, request, argument):
        result = self.libc.ioctl(self.fd, request, argument)
        if result < 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code))
        return result

    def transaction(self, address, payload, count=0):
        if (type(address) is not int or address not in ADDRESSES or type(count) is not int
                or not 0 <= count <= 40 or not 1 <= len(payload) <= 8):
            raise ValueError('Only approved touch transactions are supported')
        payload = bytes(payload)
        if self.fd is None:
            raise RuntimeError('PS I2C is closed')
        self._ownership()
        tx = (ctypes.c_uint8 * len(payload)).from_buffer_copy(payload)
        rx = (ctypes.c_uint8 * count)()
        length = 2 if count else 1
        messages = (I2CMessage * length)()
        messages[0] = I2CMessage(address, 0, len(payload), tx)
        if count:
            messages[1] = I2CMessage(address, I2C_M_RD, count, rx)
        transfer = I2CTransfer(messages, length)
        # 一个 ioctl 生成组合 START/重复 START/STOP，不改 adapter 全局超时或重试。
        try:
            result = self._ioctl(I2C_RDWR, ctypes.byref(transfer))
        except OSError as exc:
            raise OSError(exc.errno, 'PS_I2C addr=0x%02x reg=%s count=%d: %s' %
                          (address, payload.hex(), count, exc.strerror)) from exc
        if result != length:
            raise IOError('PS_I2C short message transfer: %d/%d; no retry' % (result, length))
        return bytes(rx)

    def close(self):
        fd, self.fd = self.fd, None
        try:
            if fd is not None:
                os.close(fd)
        finally:
            if self.owner is not None:
                self.owner.close()
                self.owner = None
