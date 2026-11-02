"""In-memory negative variants check the independent critical assertions."""
import contextlib
import io
import types
import unittest
from unittest.mock import patch
import test_control as tests

source = (tests.ROOT/'runtime/software/screen/backend.py').read_text(encoding='utf-8')
variants = [
    ('ignore-active-registers', "return not (value['status']", "return True or not (value['status']",
     tests.StopTests, 'test_all_idle_fields_and_activity_bits'),
    ('accept-duplicate-status', 'len(self.status_rows) == 1', 'len(self.status_rows) >= 1',
     tests.StopTests, 'test_missing_duplicate_bad_json_nonzero_and_active_status_block'),
    ('parse-history-as-current', "current = line.split(';', 1)[0]", 'current = line',
     tests.TelemetryTests, 'test_actual_formatter_current_history_nooutput_and_unobservable'),
    ('ttl-grows-with-age', "t.get('remain', 0.) - age", "t.get('remain', 0.) + age",
     tests.TelemetryTests, 'test_actual_speaker_low_score_old_permission_age_and_expiry'),
]

detected = 0
for label, before, after, cls, method in variants:
    assert source.count(before) == 1, label
    candidate = types.ModuleType('negative_backend')
    exec(compile(source.replace(before, after), label, 'exec'), candidate.__dict__)
    with patch.object(tests.be, 'Backend', candidate.Backend), contextlib.redirect_stdout(io.StringIO()):
        result = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.TestSuite([cls(method)]))
    assert result.failures and not result.errors, (label, result.failures, result.errors)
    detected += 1
    print('DETECTED='+label)

before = 'for name in reversed(changed):'
assert tests.INSTALLER.decode().count(before) == 1
negative_installer = types.ModuleType('negative_installer')
exec(compile(tests.INSTALLER.decode().replace(before, 'for name in (): '),
             'skip-install-rollback', 'exec'), negative_installer.__dict__)
with patch.object(tests, 'installer', negative_installer), contextlib.redirect_stdout(io.StringIO()):
    suite = unittest.TestSuite([tests.InstallerTests('test_six_replace_failure_positions_restore_exact_originals')])
    result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
assert result.failures and not result.errors, (result.failures, result.errors)
detected += 1
print('DETECTED=skip-install-rollback')
print('NEGATIVE_VARIANTS_DETECTED=%d/5 PRODUCT_FILES_CHANGED=0' % detected)
