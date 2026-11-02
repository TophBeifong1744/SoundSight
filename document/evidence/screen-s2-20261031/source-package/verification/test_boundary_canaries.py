"""In-memory incorrect implementations must fail host acceptance assertions."""
import contextlib
import io
import json
from pathlib import Path
import unittest
import test_linux_boundary as tests

CASES=[
 ('short-transfer-accepted',tests.li,'if result != length:','if False:','TransferTests.test_write_one_message_and_short_transfer_no_retry'),
 ('read-message-flag-removed',tests.li,'I2CMessage(address, I2C_M_RD, count, rx)','I2CMessage(address, 0, count, rx)','TransferTests.test_native_layout_and_combined_exact_pointer_and_read'),
 ('claimed-client-ignored',tests.li,'if clients:\n','if False:\n','DiscoveryTests.test_pinctrl_or_runtime_client_or_driver_mismatch_rejected'),
 ('GPIO-before-ownership',tests.ui,'bus = LinuxI2C()','gpio = ScreenGPIO(mmio(0x41200000, 0x1000))\n        bus = LinuxI2C()','LifecycleTests.test_bus_rejected_no_GPIO_and_poll_error_closes_every_owner'),
 ('EMIO-parameter-not-checked',tests.hw,'def check_ps_parameters(parameters):','def check_ps_parameters(parameters):\n    return','MetadataTests.test_actual_HWH_bad_EMIO_connection_or_parameter_rejected'),
]


def main():
    records=[]
    for name,mod,before,after,test in CASES:
        source=Path(mod.__file__).read_text(encoding='utf-8')
        assert source.count(before)==1,(name,source.count(before))
        saved=dict(mod.__dict__)
        try:
            exec(compile(source.replace(before,after),'<canary:'+name+'>','exec'),mod.__dict__)
            output=io.StringIO()
            with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
                result=unittest.TextTestRunner(stream=output).run(unittest.defaultTestLoader.loadTestsFromName(test,tests))
            detected=bool(result.failures) and not result.errors
            records.append(dict(name=name,checker=test,detected=detected,assertion_failures=len(result.failures),errors=len(result.errors),output=output.getvalue()))
            print(name+': '+('DETECTED' if detected else 'FAILED_CANARY'))
        finally:
            mod.__dict__.clear();mod.__dict__.update(saved)
    (tests.HERE/'canary-results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    return 0 if all(x['detected'] for x in records) else 1


if __name__=='__main__':raise SystemExit(main())
