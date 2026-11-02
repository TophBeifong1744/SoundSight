"""Screen S1: byte offsets, 32-bit MMIO, packed BGR, no overlay downloads."""
import time


def wait_until(predicate, timeout, reason):
    # 所有外设等待均有截止时间；总线本身失去 AXI 响应不属于软件可恢复故障。
    end = time.monotonic() + timeout
    while True:
        if predicate():
            return
        if time.monotonic() >= end:
            raise TimeoutError(reason)
        time.sleep(.0005)


class ScreenGPIO:
    RST, INT, BL = 1, 2, 4

    def __init__(self, mmio, touch_owned=True):
        self.mmio = mmio
        # A startup error screen can own video/backlight before the I2C bus.
        # In that case preserve the touch reset/INT latches and directions.
        self.output = mmio.read(0)
        if touch_owned:
            self.output &= ~7
        self.direction = mmio.read(4)
        self.pin(self.BL, False, output=True)
        if touch_owned:
            self.pin(self.INT, False, output=False)

    def pin(self, mask, high, output=True):
        # 仅修改本屏幕拥有的三个引脚；先置输出锁存，再改变三态。
        if mask not in (self.RST, self.INT, self.BL):
            raise ValueError('Unknown screen GPIO bit')
        self.output = (self.output | mask) if high else (self.output & ~mask)
        self.mmio.write(0, self.output)
        self.direction = (self.direction & ~mask) if output else (self.direction | mask)
        self.mmio.write(4, self.direction)
        self.mmio.read(4)

    def backlight(self, on):
        self.pin(self.BL, on)

    def locked(self):
        return bool(self.mmio.read(8) & 1)


class Touch:
    def __init__(self, bus, gpio, swap=False, invert_x=False, invert_y=False):
        self.bus, self.gpio = bus, gpio
        self.swap, self.invert_x, self.invert_y = swap, invert_x, invert_y
        self.kind, self.address, self.product = None, None, ''

    def reset(self, address=None):
        # 保留旧屏幕已验证的复位时序；Goodix 地址仅通过 INT 复位选择。
        g = self.gpio
        g.pin(g.INT, False, output=False)
        g.pin(g.RST, False)
        if address is not None:
            g.pin(g.INT, address == 0x14)
        time.sleep(.020)
        g.pin(g.RST, True)
        time.sleep(.200 if address is None else .060)
        g.pin(g.INT, False, output=False)
        if address is not None:
            time.sleep(.050)

    def read(self, register, count, address=None, goodix=None):
        address = self.address if address is None else address
        goodix = self.kind == 'Goodix' if goodix is None else goodix
        pointer = register.to_bytes(2 if goodix else 1, 'big')
        return self.bus.transaction(address, pointer, count)

    def probe(self):
        self.reset()
        for reset_address, candidates in ((None, (0x38, 0x5d, 0x14)),
                                           (0x5d, (0x5d,)), (0x14, (0x14,))):
            if reset_address is not None:
                self.reset(reset_address)
            for address in candidates:
                try:
                    if address == 0x38:
                        if self.read(2, 1, address, False)[0] & 15 > 5:
                            continue
                        self.kind, self.product = 'FT5x06/CST340-compatible', 'FT??'
                        try:
                            self.product = 'FT%02X' % self.read(0xa3, 1, address, False)[0]
                        except (IOError, TimeoutError):
                            pass
                    else:
                        ident = self.read(0x8140, 4, address, True)
                        if sum((48 <= c <= 57 or 65 <= c <= 90 or 97 <= c <= 122) for c in ident) < 3:
                            continue
                        self.kind, self.product = 'Goodix', ident.decode('ascii', errors='replace')
                    self.address = address
                    return self.kind + ' ' + self.product + ' @0x%02X' % address
                except (IOError, TimeoutError):
                    continue
        self.reset()
        # 与旧驱动一致：Goodix 地址尝试失败后，再以通用复位确认一次 0x38。
        try:
            if self.read(2, 1, 0x38, False)[0] & 15 <= 5:
                self.address, self.kind, self.product = 0x38, 'FT5x06/CST340-compatible', 'FT??'
                return self.kind + ' ' + self.product + ' @0x38'
        except (IOError, TimeoutError):
            pass
        raise IOError('No supported Goodix or FT5x06/CST340-compatible touch detected')

    def poll(self):
        # 返回 None 表示 Goodix 无新帧，[] 表示明确抬手；不能混淆两者。
        goodix = self.kind == 'Goodix'
        status = self.read(0x814e if goodix else 2, 1)[0]
        if goodix and not status & 0x80:
            return None
        count = status & 15
        if count > 5:
            if goodix:
                self.bus.transaction(self.address, b'\x81\x4e\x00')
            raise IOError('Invalid touch point count')
        data = self.read(0x814f if goodix else 3, count * (8 if goodix else 6)) if count else b''
        if goodix:
            self.bus.transaction(self.address, b'\x81\x4e\x00')
        points = []
        for i in range(count):
            p = data[i*(8 if goodix else 6):]
            if goodix:
                x, y = p[1] | p[2] << 8, p[3] | p[4] << 8
            else:
                if p[0] >> 6 == 1:
                    continue
                if p[0] >> 6 == 3:
                    raise IOError('Reserved FT touch event')
                x, y = (p[0] & 15) << 8 | p[1], (p[2] & 15) << 8 | p[3]
            if self.swap:
                x, y = y, x
            if self.invert_x:
                x = 799-x
            if self.invert_y:
                y = 479-y
            # 越界不生成边缘按钮点击，保留首次角落校准的错误证据。
            if not 0 <= x < 800 or not 0 <= y < 480:
                raise IOError('Touch coordinate out of range: %s,%s' % (x, y))
            points.append((x, y))
        return points


class Display:
    ERRORS = 0xff0

    def __init__(self, mmio, gpio, allocate, numpy):
        self.mmio, self.gpio, self.np = mmio, gpio, numpy
        self.buffers, self.active, self.live = [], 0, False

    def start(self, allocate):
        # 分离初始化和启动，任一步失败时调用者仍持有缓冲所有权以完成清理。
        mmio = self.mmio
        self.gpio.backlight(False)
        version = mmio.read(0x2c)
        if version >> 28 != 6:
            raise ValueError('Expected VDMA major version 6, got 0x%x' % version)
        if not mmio.read(4) & 1:
            raise RuntimeError('VDMA already running; preserve existing buffers/owner')
        mmio.write(0, 4)
        wait_until(lambda: not mmio.read(0) & 4, .25, 'VDMA reset timeout')
        for _ in range(2):
            b = allocate(shape=(480, 800, 3), dtype=self.np.uint8)
            self.buffers.append(b)
            if int(b.physical_address) % 8 or not 0 <= int(b.physical_address) <= 0x40000000-1152000:
                raise ValueError('VDMA buffer must fit aligned HP1 DDR aperture [0, 0x40000000)')
            b[:] = 0
            b.flush()
        mmio.write(0x5c, int(self.buffers[0].physical_address))
        mmio.write(0x60, int(self.buffers[1].physical_address))
        mmio.write(0x28, mmio.read(0x28) & 0x1f00)
        mmio.write(0x58, 2400)
        mmio.write(0x54, 2400)
        self.live = True
        mmio.write(0, 1)  # Park mode, no genlock/IRQ/frame-count stop.
        mmio.write(0x50, 480)  # VSIZE last: starts the configured transfer.
        wait_until(lambda: not mmio.read(4) & 1, .25, 'VDMA start timeout')
        print('VDMA_STARTED version=0x%x frame0=0x%x frame1=0x%x stride=2400 height=480' %
              (version, int(self.buffers[0].physical_address), int(self.buffers[1].physical_address)), flush=True)

    def health(self):
        status = self.mmio.read(4)
        if status & (self.ERRORS | 1):
            raise IOError('VDMA halted/error SR=0x%x' % status)
        if not self.gpio.locked():
            raise IOError('Screen video output timing lock lost')

    def present(self, rgb):
        # CPU 只写非当前帧；flush 完成后交接给 DMA，ACK 前不复用旧帧。
        self.health()
        target = 1-self.active
        if (self.mmio.read(0x28) >> 16) & 31 != self.active:
            raise IOError('VDMA park ownership mismatch')
        self.buffers[target][:] = self.np.asarray(rgb, dtype=self.np.uint8)[:, :, ::-1]
        self.buffers[target].flush()
        self.mmio.write(0x28, (self.mmio.read(0x28) & 0x1f00) | target)
        wait_until(lambda: ((self.mmio.read(0x28) >> 16) & 31) == target,
                   .25, 'VDMA current frame acknowledgement timeout')
        self.health()
        self.active = target

    def close(self):
        try:
            self.gpio.backlight(False)
        except Exception:
            pass  # GPIO 故障不能阻止后续 DMA 停止尝试。
        if self.live:
            try:
                self.mmio.write(0, self.mmio.read(0) & ~1)
                try:
                    wait_until(lambda: self.mmio.read(4) & 1, .25, 'VDMA stop timeout')
                except TimeoutError:
                    self.mmio.write(0, 4)
                    wait_until(lambda: not self.mmio.read(0) & 4 and self.mmio.read(4) & 1,
                               .25, 'VDMA recovery timeout')
            except Exception:
                return False  # 活 DMA 缓冲仍归本进程所有，禁止释放或退出。
            self.live = False
            print('VDMA_STOPPED=1 HALTED_ACK=1 BACKLIGHT_REQUEST=OFF', flush=True)
        while self.buffers:
            self.buffers[-1].freebuffer()
            self.buffers.pop()
        return True


def verify_install(root):
    # 安装身份和重启门禁在所有新地址访问之前生效。
    import hashlib
    import json
    from pathlib import Path
    root = Path(root).resolve()
    path = root/'SCREEN-INSTALL.json'
    if not path.is_file() or path.stat().st_size > 65536:
        raise ValueError('Missing/oversized S2 SCREEN-INSTALL.json')
    receipt = json.loads(path.read_text(encoding='utf-8'))
    if receipt.get('revision') != 'SCREEN_PS_I2C_S2' or receipt.get('touch_transport') != 'PS_I2C0_EMIO_LINUX':
        raise ValueError('Install matched SCREEN_PS_I2C_S2 package first')
    boot = receipt.get('installed_boot_id')
    if not isinstance(boot, str) or not boot.strip() or boot.strip() == Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        raise ValueError('Reboot after S2 installation, then run soundsight-3d.sh prepare')
    for group, names in (('hardware', ('soundsight.bit', 'soundsight.hwh')),
                         ('software', ('software/screen/hardware.py', 'software/screen/ui.py',
                                       'software/screen/linux_i2c.py', 'software/screen/screen_i2c_prepare.py',
                                       'software/screen/ps_i2c0_enable.dtbo'))):
        for name in names:
            expected = receipt.get(group, {}).get(name)
            if not isinstance(expected, str) or len(expected) != 64 or hashlib.sha256((root/name).read_bytes()).hexdigest() != expected:
                raise ValueError('S2 installed file hash mismatch: '+name)
    return receipt


def check_ps_parameters(parameters):
    for name, value in (('PCW_I2C0_PERIPHERAL_ENABLE', '1'), ('PCW_I2C0_I2C0_IO', 'EMIO'),
                        ('PCW_I2C0_GRP_INT_ENABLE', '1'), ('PCW_I2C0_GRP_INT_IO', 'EMIO')):
        if str(parameters.get(name)) != value:
            raise ValueError('S2 PS I2C0/EMIO parameter mismatch: '+name)
    if int(str(parameters.get('PCW_I2C0_BASEADDR', '-1')), 0) != 0xe0004000:
        raise ValueError('S2 PS I2C0 base mismatch')


def check_s2_metadata(overlay, root):
    from pathlib import Path
    device = overlay.device
    if Path(getattr(device, 'bitfile_name', '')).resolve() != (root/'soundsight.bit').resolve() or not getattr(device, 'timestamp', ''):
        raise ValueError('No matching loaded bitfile path/timestamp; prepare S2 first')
    loaded = device.ip_dict
    if not isinstance(loaded, dict):
        raise ValueError('Loaded device metadata unavailable')
    for origin, dictionary in (('disk', overlay.ip_dict), ('loaded', loaded)):
        if 'screen_iic' in dictionary:
            raise ValueError('S2 rejects old screen_iic IP instance in '+origin+' metadata')
        for info in dictionary.values():
            if ':axi_iic:' in info.get('type', '') or info.get('phys_addr') == 0x41600000:
                raise ValueError('S2 rejects old AXI IIC in '+origin+' metadata')
        for name, base, kind in (('screen_vdma', 0x43000000, 'axi_vdma'),
                                 ('screen_gpio', 0x41200000, 'axi_gpio')):
            info = dictionary.get(name, {})
            if info.get('phys_addr') != base or ':'+kind+':' not in info.get('type', '') or info.get('addr_range', 0) < 0x1000:
                raise ValueError('S2 '+origin+' screen mapping mismatch: '+name)
        params = dictionary['screen_vdma'].get('parameters', {})
        for key, value in (('C_INCLUDE_MM2S', 1), ('C_INCLUDE_S2MM', 0), ('C_NUM_FSTORES', 2),
                           ('C_M_AXI_MM2S_DATA_WIDTH', 64), ('C_M_AXIS_MM2S_TDATA_WIDTH', 24), ('C_INCLUDE_SG', 0)):
            if int(str(params.get(key, '-1')), 0) != value:
                raise ValueError('S2 '+origin+' VDMA parameter mismatch: '+key)
        processors = [p for p in dictionary.values() if ':processing_system7:' in p.get('type', '')]
        if len(processors) > 1:
            raise ValueError('Ambiguous PS7 metadata')
        if processors:
            check_ps_parameters(processors[0].get('parameters', {}))
    # 官方 PYNQ 2.7 HWH parser.root 是磁盘解析结果，不伪称为硬件寄存器读回。
    # 已加载路径/时间戳/无 AXI IIC 的 PL 快照与安装哈希提供独立身份约束。
    parser_root = getattr(getattr(overlay, 'parser', None), 'root', None)
    if parser_root is None:
        raise ValueError('PYNQ HWH parser.root unavailable')
    modules = list(parser_root.iter('MODULE'))
    if any(m.get('MODTYPE') == 'axi_iic' for m in modules):
        raise ValueError('S2 parser still contains AXI IIC')
    processors = [m for m in modules if m.get('MODTYPE') == 'processing_system7']
    if len(processors) != 1:
        raise ValueError('Expected one PS7 in HWH parser')
    processor = processors[0]
    check_ps_parameters({p.get('NAME'): p.get('VALUE') for p in processor.iter('PARAMETER')})
    internal = [b for b in processor.iter('BUSINTERFACE') if b.get('NAME') == 'IIC_0']
    external = [b for b in parser_root.findall('./EXTERNALINTERFACES/BUSINTERFACE') if b.get('NAME') == 'screen_iic']
    if len(internal) != 1 or len(external) != 1 or not internal[0].get('BUSNAME') or internal[0].get('BUSNAME') != external[0].get('BUSNAME'):
        raise ValueError('PS IIC_0 to screen_iic connection not established by HWH')


def open_overlay(root):
    # 仅接管已由原 prepare 命令准备的匹配硬件，不重新下载位流。
    from pathlib import Path
    root = Path(root).resolve()
    verify_install(root)
    from pynq import Overlay, MMIO, allocate
    import numpy as np
    overlay = Overlay(str(root/'soundsight.bit'), download=False)
    if not overlay.is_loaded():
        raise RuntimeError('Run soundsight-3d.sh prepare before starting the screen')
    check_s2_metadata(overlay, root)
    # 复用原只读时钟/ABI/空闲检查；保留其现有 100 MHz 与 fault 判据。
    import sys
    sys.path.insert(0, str(root/'software/ps'))
    import board_tools
    from run_capture import single_owner
    with single_owner('/tmp/soundsight-ps-owner.lock'):
        state = board_tools.inspect_loaded(root)
        board_tools.require_idle(state)
    print('SCREEN_PREFLIGHT=' + str(state), flush=True)
    return overlay, MMIO, allocate, np
