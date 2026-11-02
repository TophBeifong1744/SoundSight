"""Independent host tests of new Linux boundary, using native ctypes ABI fixtures."""
import contextlib
import copy
import ctypes
import errno
import importlib
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET
import numpy
import PIL

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parent/'ss-screen-ps-i2c-ui-s2/software/screen'
if not PRODUCT.is_dir(): PRODUCT = HERE.parent/'screen-ui/software/screen'
HWH = HERE.parent/'ss-screen-ps-i2c-s2/output/soundsight.hwh'
if not HWH.is_file(): HWH = HERE.parent/'output/soundsight.hwh'
sys.path.insert(0,str(PRODUCT))
li, hw, ui, setup = [importlib.import_module(x) for x in ('linux_i2c','hardware','ui','screen_i2c_prepare')]


# Linux include/uapi/linux/i2c.h and i2c-dev.h; native alignment, no packing.
class NativeMessage(ctypes.Structure):
    _fields_=[('address',ctypes.c_uint16),('flags',ctypes.c_uint16),('length',ctypes.c_uint16),('data',ctypes.POINTER(ctypes.c_uint8))]
class NativeTransfer(ctypes.Structure):
    _fields_=[('messages',ctypes.POINTER(NativeMessage)),('count',ctypes.c_uint32)]


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=HERE,prefix='linux_')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.dt,self.sy,self.dev=[self.root/x for x in ('dt','sys','dev')]
        self.node=self.dt/'amba/i2c@e0004000'
        self.platform=self.sy/'bus/platform/devices/e0004000.i2c'
        self.adapter=self.sy/'class/i2c-adapter/i2c-7'
        self.realplatform=self.sy/'devices/platform/amba/e0004000.i2c'
        self.realadapter=self.realplatform/'i2c-7'
        self.driver=self.sy/'bus/platform/drivers/cdns-i2c'
        for p in (self.node,self.platform/'of_node',self.platform/'driver',self.adapter/'of_node',self.realadapter,self.realplatform/'of_node',self.realplatform/'driver',self.driver,self.dev,self.sy/'bus/i2c/devices'):
            p.mkdir(parents=True,exist_ok=True)
        self.links={self.platform:self.realplatform,self.platform/'of_node':self.node,self.platform/'driver':self.driver,
                    self.adapter:self.realadapter,self.adapter/'of_node':self.node,
                    self.realplatform/'of_node':self.node,self.realplatform/'driver':self.driver}
        real_resolve=Path.resolve
        def resolve(p,*args,**kwargs): return real_resolve(self.links.get(p,p),*args,**kwargs)
        rp=patch.object(Path,'resolve',resolve)
        rp.start(); self.addCleanup(rp.stop)
        self.prop(self.node.parent,'#address-cells',[1]);self.prop(self.node.parent,'#size-cells',[1])
        for name,value in {'reg':[0xe0004000,0x1000],'clocks':[4,38],'interrupts':[0,25,4],'clock-frequency':[100000],
                           'compatible':b'cdns,i2c-r1p10\0','status':b'okay\0'}.items(): self.prop(self.node,name,value)
        provider=self.dt/'amba/slcr/clkc';provider.mkdir(parents=True)
        self.prop(provider,'phandle',[4]);self.prop(provider,'compatible',b'xlnx,ps7-clkc\0')
        (self.dev/'i2c-7').write_bytes(b'fixture device node, fstat mocked separately')

    def prop(self,node,name,value):
        (node/name).write_bytes(b''.join(x.to_bytes(4,'big') for x in value) if isinstance(value,list) else value)

    def adapter_info(self): return li.find_adapter(self.dt,self.sy,self.dev)


class DiscoveryTests(Fixture):
    def test_actual_node_identity_selects_bus7_not_number0(self):
        info=self.adapter_info()
        self.assertEqual((info['bus'],info['reg'],info['driver']),(7,[0xe0004000,0x1000],'cdns-i2c'))

    def test_DT_disabled_wrong_address_clock_and_client_rejected(self):
        cases=[('status',b'disabled\0','NOT_READY'),('reg',[0xe0005000,0x1000],'IDENTITY_MISMATCH'),
               ('clock-frequency',[400000],'NOT_READY'),('interrupts',[0,26,4],'CLOCK_IRQ_UNCONFIRMED')]
        for key,value,reason in cases:
            with self.subTest(key=key):
                original=(self.node/key).read_bytes();self.prop(self.node,key,value)
                with self.assertRaisesRegex(RuntimeError,reason):self.adapter_info()
                self.prop(self.node,key,original)
        client=self.node/'touch@14';client.mkdir();self.prop(client,'reg',[0x14])
        with self.assertRaisesRegex(RuntimeError,'DT_CLIENTS_PRESENT'):self.adapter_info()

    def test_pinctrl_or_runtime_client_or_driver_mismatch_rejected(self):
        self.prop(self.node,'pinctrl-names',b'default\0')
        with self.assertRaisesRegex(RuntimeError,'PINCTRL_PRESENT'):self.adapter_info()
        (self.node/'pinctrl-names').unlink()
        client=self.sy/'bus/i2c/devices/7-0014';client.mkdir()
        with self.assertRaisesRegex(RuntimeError,'BUS_HAS_CLIENTS'):self.adapter_info()
        client.rmdir()
        self.links[self.platform/'driver']=self.sy/'drivers/unrelated'
        with self.assertRaisesRegex(RuntimeError,'CADENCE_DRIVER_MISSING'):self.adapter_info()

    def test_runtime_ownership_change_blocks_before_ioctl(self):
        bus=li.LinuxI2C.__new__(li.LinuxI2C)
        bus.details=self.adapter_info();bus.dt_root,bus.sys_root,bus.dev_root=self.dt,self.sy,self.dev
        bus.fd=99;bus._ioctl=Mock()
        (self.sy/'bus/i2c/devices/7-0038').mkdir()
        with self.assertRaisesRegex(RuntimeError,'OWNERSHIP_CHANGED'):bus.transaction(0x14,b'\x81\x4e',1)
        bus._ioctl.assert_not_called()


class TransferTests(unittest.TestCase):
    def bus(self):
        b=li.LinuxI2C.__new__(li.LinuxI2C)
        b.fd,b.owner=99,None
        b._ownership=Mock()
        return b

    def test_native_layout_and_combined_exact_pointer_and_read(self):
        details=li.abi_details()
        self.assertEqual(ctypes.sizeof(li.I2CMessage),ctypes.sizeof(NativeMessage))
        self.assertEqual(ctypes.sizeof(li.I2CTransfer),ctypes.sizeof(NativeTransfer))
        self.assertEqual(details['buf_offset'],8)
        b=self.bus();calls=[]
        def ioctl(request,arg):
            transfer=ctypes.cast(arg,ctypes.POINTER(NativeTransfer)).contents
            calls.append(request)
            self.assertEqual(request,0x707)
            self.assertEqual(transfer.count,2)
            a,c=transfer.messages[0],transfer.messages[1]
            self.assertEqual((a.address,a.flags,a.length),(0x14,0,2))
            self.assertEqual(bytes(a.data[:a.length]),b'\x81\x4e')
            self.assertEqual((c.address,c.flags,c.length),(0x14,1,4))
            for i,v in enumerate(b'911\0'):c.data[i]=v
            return 2
        b._ioctl=ioctl
        self.assertEqual(b.transaction(0x14,b'\x81\x4e',4),b'911\0')
        self.assertEqual(calls,[0x707])

    def test_write_one_message_and_short_transfer_no_retry(self):
        b=self.bus()
        def write_ioctl(request,arg):
            t=ctypes.cast(arg,ctypes.POINTER(NativeTransfer)).contents
            self.assertEqual(t.count,1)
            m=t.messages[0]
            self.assertEqual((m.address,m.flags,m.length),(0x14,0,3))
            self.assertEqual(bytes(m.data[:m.length]),b'\x81\x4e\0')
            return 1
        b._ioctl=write_ioctl
        self.assertEqual(b.transaction(0x14,b'\x81\x4e\0'),b'')
        b._ioctl=Mock(return_value=1)
        with self.assertRaisesRegex(IOError,'short message transfer'):b.transaction(0x14,b'\x81\x4e',1)
        b._ioctl.assert_called_once()

    def test_errno_preserved_no_data_return_and_invalid_bounds(self):
        b=self.bus();b._ioctl=Mock(side_effect=OSError(errno.ENXIO,'no acknowledgement'))
        with self.assertRaises(OSError) as caught:b.transaction(0x14,b'\x81\x4e',1)
        self.assertEqual(caught.exception.errno,errno.ENXIO)
        b._ioctl.assert_called_once()
        b._ioctl.reset_mock()
        for address,payload,count in ((0x50,b'x',1),(0x14,b'',1),(0x14,b'x'*9,1),(0x14,b'x',41)):
            with self.assertRaises(ValueError):b.transaction(address,payload,count)
        b._ioctl.assert_not_called()

    def test_close_is_idempotent(self):
        b=self.bus();owner=b.owner=Mock()
        with patch.object(li.os,'close') as close:
            b.close();b.close();close.assert_called_once_with(99)
        owner.close.assert_called_once()
        self.assertIsNone(b.fd)


class ConstructorTests(Fixture):
    def construct(self,capable=True,minor=7):
        owner=Mock();clib=Mock()
        def ioctl(fd,request,arg):
            self.assertEqual((fd,request),(77,0x705))
            ctypes.cast(arg,ctypes.POINTER(ctypes.c_ulong))[0]=1 if capable else 0
            return 0
        clib.ioctl.side_effect=ioctl
        fakeos=types.SimpleNamespace(O_RDWR=2,O_CLOEXEC=0x80000,open=Mock(return_value=77),close=Mock(),
            fstat=Mock(return_value=types.SimpleNamespace(st_mode=stat.S_IFCHR,st_rdev=123)),
            major=lambda dev:89,minor=lambda dev:minor,strerror=lambda code:'fixture errno')
        fc=types.ModuleType('fcntl');fc.LOCK_EX,fc.LOCK_NB=1,2;fc.flock=Mock()
        with patch.object(li,'open',Mock(return_value=owner),create=True),patch.object(li,'os',fakeos),patch.object(li.ctypes,'CDLL',return_value=clib),patch.dict(sys.modules,{'fcntl':fc}):
            if capable and minor==7:
                b=li.LinuxI2C(self.dt,self.sy,self.dev)
                self.assertEqual(b.fd,77)
                self.assertEqual(clib.ioctl.call_count,1)
                b.close()
            else:
                with self.assertRaises(RuntimeError):li.LinuxI2C(self.dt,self.sy,self.dev)
            fakeos.close.assert_called_once_with(77)
            owner.close.assert_called_once()
        return clib

    def test_open_checks_character_identity_and_capabilities_without_probe(self):
        self.construct()

    def test_failed_capability_or_device_identity_closes_fd_and_owner(self):
        self.construct(capable=False)
        self.assertEqual(self.construct(minor=8).ioctl.call_count,0)


class PrepareTests(unittest.TestCase):
    def test_wrong_frequency_and_unknown_status_do_not_insert(self):
        with tempfile.TemporaryDirectory(dir=HERE,prefix='prepare_') as root:
            for info,reason in (({'status':'okay','clock_frequency':[400000]},'WRONG_FREQUENCY'),
                                ({'status':'reserved'},'UNKNOWN_DT_STATUS')):
                with self.subTest(info=info),patch.object(setup,'node_details',return_value=info),patch.object(setup,'check_bus') as check:
                    with self.assertRaisesRegex(RuntimeError,reason):setup.apply_overlay(Path(root))
                    check.assert_not_called()

    def test_already_ready_uses_capability_check_no_overlay_mutation(self):
        with patch.object(setup,'node_details',return_value={'status':'okay','clock_frequency':[100000]}),patch.object(setup,'check_bus',return_value={'transfer_performed':False}) as check:
            self.assertEqual(setup.apply_overlay(HERE),{'action':'already_enabled','transfer_performed':False})
            check.assert_called_once()


def real_hwh_fixture():
    ps=types.ModuleType('pynq.ps')
    ps.CPU_ARCH_IS_SUPPORTED=True
    ps.CPU_ARCH=ps.ZYNQ_ARCH='armv7l';ps.ZU_ARCH='aarch64'
    with patch.dict(sys.modules,{'pynq.ps':ps}):
        parser_module=importlib.import_module('vendor_hwh_parser_pynq270')
        parser=parser_module.HWH(hwh_name=str(HWH))
    return parser.root,parser.ip_dict


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.root=HERE/'runtime-reference'
        parser,dictionary=real_hwh_fixture()
        self.overlay=types.SimpleNamespace(ip_dict=dictionary,parser=types.SimpleNamespace(root=parser),
            device=types.SimpleNamespace(ip_dict=copy.deepcopy(dictionary),bitfile_name=str(self.root/'soundsight.bit'),timestamp='actual-load-token-fixture'))

    def test_actual_generated_HWH_passes_PS_connection_and_parameters(self):
        hw.check_s2_metadata(self.overlay,self.root)
        self.assertNotIn('screen_iic',self.overlay.ip_dict)

    def test_old_loaded_AXI_IIC_and_wrong_loaded_path_rejected(self):
        self.overlay.device.ip_dict['screen_iic']=dict(type='xilinx.com:ip:axi_iic:2.1',phys_addr=0x41600000)
        with self.assertRaisesRegex(ValueError,'rejects old'):hw.check_s2_metadata(self.overlay,self.root)
        self.overlay.device.ip_dict.pop('screen_iic')
        self.overlay.device.bitfile_name=str(self.root/'other.bit')
        with self.assertRaisesRegex(ValueError,'matching loaded'):hw.check_s2_metadata(self.overlay,self.root)

    def test_actual_HWH_bad_EMIO_connection_or_parameter_rejected(self):
        for kind in ('connection','parameter'):
            with self.subTest(kind=kind):
                self.setUp()
                if kind=='connection':
                    x=self.overlay.parser.root.find("./EXTERNALINTERFACES/BUSINTERFACE[@NAME='screen_iic']")
                    x.set('BUSNAME','wrong_bus')
                else:
                    for p in self.overlay.parser.root.iter('PARAMETER'):
                        if p.get('NAME')=='PCW_I2C0_I2C0_IO':p.set('VALUE','MIO')
                with self.assertRaises(ValueError):hw.check_s2_metadata(self.overlay,self.root)


class LifecycleTests(unittest.TestCase):
    def run_main(self,bus_fail=False,poll_fail=False):
        events=[]
        bus=Mock(details={'bus':7});bus.close.side_effect=lambda:events.append('bus-close')
        def open_bus():
            events.append('bus-check')
            if bus_fail:raise RuntimeError('ownership refused')
            return bus
        gpio=Mock();gpio.locked.return_value=True
        gpio.backlight.side_effect=lambda value:events.append('light-'+str(value))
        def make_gpio(mm):events.append('gpio');return gpio
        display=Mock(active=1)
        display.start.side_effect=lambda allocate:events.append('dma-start')
        display.present.side_effect=lambda frame:events.append('frame-ack')
        display.close.side_effect=lambda:events.append('dma-close') or True
        touch=Mock()
        touch.probe.side_effect=lambda:events.append('touch-reset-probe') or 'Goodix911'
        touch.poll.side_effect=IOError('injected ioctl failure') if poll_fail else None
        if not poll_fail:touch.poll.return_value=[]
        clock=types.SimpleNamespace(now=0.)
        clock.monotonic=lambda:clock.now
        def sleep(t):clock.now+=t
        clock.sleep=sleep
        fc=types.ModuleType('fcntl');fc.LOCK_EX,fc.LOCK_NB,fc.LOCK_UN=1,2,4;fc.flock=Mock()
        with tempfile.TemporaryDirectory(dir=HERE,prefix='lifecycle_') as root,contextlib.ExitStack() as stack:
            patches=[patch.object(ui,'os',types.SimpleNamespace(name='posix')),patch.object(ui,'time',clock),
                patch.object(ui.signal,'signal'),patch.object(ui,'open',Mock(return_value=Mock()),create=True),patch.dict(sys.modules,{'fcntl':fc}),
                patch.object(hw,'open_overlay',return_value=(Mock(),Mock(),Mock(),Mock())),patch.object(li,'LinuxI2C',open_bus),
                patch.object(hw,'ScreenGPIO',make_gpio),patch.object(hw,'Display',Mock(return_value=display)),patch.object(hw,'Touch',Mock(return_value=touch))]
            for p in patches:stack.enter_context(p)
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()));stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            result=ui.main(['--root',root,'--seconds','.04'])
        return result,events

    def test_bus_checked_before_GPIO_probe_and_closed_after_DMA(self):
        result,events=self.run_main()
        self.assertEqual(result,0)
        self.assertLess(events.index('bus-check'),events.index('gpio'))
        self.assertLess(events.index('bus-check'),events.index('touch-reset-probe'))
        self.assertLess(events.index('frame-ack'),events.index('light-True'))
        self.assertLess(events.index('dma-close'),events.index('bus-close'))

    def test_bus_rejected_no_GPIO_and_poll_error_closes_every_owner(self):
        result,events=self.run_main(bus_fail=True)
        self.assertEqual((result,events),(1,['bus-check']))
        result,events=self.run_main(poll_fail=True)
        self.assertEqual(result,1)
        self.assertEqual(events[-2:],['dma-close','bus-close'])

    def test_demo_does_not_open_Linux_I2C(self):
        with tempfile.TemporaryDirectory(dir=HERE,prefix='demo_') as root,patch.object(li,'LinuxI2C') as bus,contextlib.redirect_stdout(io.StringIO()):
            destination=Path(root)/'demo.png'
            result=ui.main(['--root',root,'--demo','--screenshot',str(destination)])
            self.assertEqual(result,0);self.assertGreater(destination.stat().st_size,1000)
            bus.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
