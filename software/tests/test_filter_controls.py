"""可调窗口及串口诊断的独立输入预期；无PYNQ或板端动作。"""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ps'))
sys.path.insert(0, str(Path(__file__).parent))
from angle_filter import OnlineAngleFilter, validate_window
from volume_gate import gate_record, VolumeClient
from test_online_angle_filter import record, feed
import run_normal as normal
import run_buffered as buffered
import board_tools as board


class FilterControlTests(unittest.TestCase):
    def test_default_output_frames_and_counts_unchanged(self):
        rows = feed(OnlineAngleFilter(), [10]*12+[None]*8+[12]*20+[13]*20)
        self.assertEqual([r['frame']['sequence'] for r in rows if r['direction_output']['valid']], [20,40,60])
        self.assertEqual([rows[i]['direction_output']['updated'] for i in (19,39,59)], [True,False,True])
        self.assertEqual([round(rows[i]['direction_output']['angle_deg']) for i in (19,39,59)], [10,10,13])

    def test_custom_size_minimum_and_wrap(self):
        rows = feed(OnlineAngleFilter(5,3), [179,-179,179,None,None]*2)
        self.assertEqual([r['frame']['sequence'] for r in rows if r['direction_output']['valid']], [5,10])
        self.assertGreater(abs(rows[4]['direction_output']['angle_deg']), 179)
        self.assertEqual(rows[4]['angle_filter']['min_valid'], 3)
        self.assertEqual(rows[4]['angle_filter']['window_size'], 5)
        rejected = feed(OnlineAngleFilter(5,4), [10]*3+[None]*2)[-1]
        self.assertEqual(rejected['direction_output']['reason'], 'insufficient_valid')

    def test_custom_minimum_applies_to_inliers_and_consensus_unchanged(self):
        row = feed(OnlineAngleFilter(6,2), [0]*3+[90]*3)[-1]
        self.assertEqual(row['direction_output']['reason'], 'insufficient_consensus')
        row = feed(OnlineAngleFilter(6,5), [0]*4+[90]*2)[-1]
        self.assertEqual(row['direction_output']['reason'], 'insufficient_consensus')

    def test_invalid_parameters_fail_before_use(self):
        for pair in [(0,0),(5,6),(101,12),(20,0),(True,1),(20,1.5)]:
            with self.assertRaises(ValueError): OnlineAngleFilter(*pair)
        self.assertEqual(validate_window(1,1), (1,1))
        self.assertEqual(validate_window(100,100), (100,100))

    def test_clear_and_gap_reasons_without_rule_changes(self):
        f = OnlineAngleFilter(5,3)
        feed(f,[0]*4)
        low = f.apply(gate_record(record(5, level=1),1000))
        self.assertEqual(low['angle_filter']['reset_reason'], 'below_volume_threshold')
        self.assertEqual(low['angle_filter']['frame_count'],0)
        gap = feed(f,[10,10],start=8)[-1]
        self.assertEqual(gap['angle_filter']['frame_count'],2)
        gap = feed(f,[10],start=12)[-1]
        self.assertEqual(gap['angle_filter']['reset_reason'],'sequence_gap')
        self.assertEqual(gap['angle_filter']['frame_count'],1)
        f.stop()
        stopped = feed(f,[10]*5,start=13)
        self.assertTrue(all(not r['direction_output']['valid'] for r in stopped))

    def test_display_retains_completed_rejection_while_next_group_collects(self):
        state = normal.RuntimeState()
        for row in feed(OnlineAngleFilter(5,3), [0,None,None,None,None,10,10]):
            state.accept(row)
        line = normal.display_line(state.snapshot())
        self.assertIn('WINDOW=2/5 VALID=2 MIN=3', line)
        self.assertIn('LAST_GROUP=INSUFFICIENT_VALID_ANGLES@5 VALID=1 KEEP=0', line)
        self.assertIn('LAST_CLEAR=NONE', line)
        self.assertTrue(line.isascii())

    def test_recent_clear_is_retained_after_recovery(self):
        f, state = OnlineAngleFilter(5,3), normal.RuntimeState()
        state.accept(f.apply(gate_record(record(1,level=1),1000)))
        for row in feed(f,[10,10],start=2): state.accept(row)
        line = normal.display_line(state.snapshot())
        self.assertIn('WINDOW=2/5',line)
        self.assertIn('LAST_CLEAR=LOW_VOLUME@1',line)
        self.assertIn('LAST_GROUP=NONE',line)

    def test_old_accepted_group_is_history_not_current_angle_after_low_volume(self):
        state, f = normal.RuntimeState(), OnlineAngleFilter(5,3)
        for row in feed(f,[20]*5): state.accept(row)
        state.accept(f.apply(gate_record(record(6,level=1),1000)))
        line = normal.display_line(state.snapshot())
        self.assertIn('NO_OUTPUT: LOW_VOLUME',line)
        self.assertIn('LAST_GROUP=ACCEPTED_UPDATED@5',line)
        self.assertIn('TARGET=20.00deg(HISTORY)',line)
        self.assertNotIn('ANGLE=',line)
        self.assertIsNone(state.window)

    def test_settings_legacy_migration_and_updates_preserve_each_other(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/board.SETTINGS).write_text('{"min_level":4200,"other":9}')
            self.assertEqual(board.get_settings(root)['window_frames'],20)
            board.set_filter(10,6,root)
            self.assertEqual(board.get_level(root),4200)
            board.set_level(5000,root)
            settings=board.get_settings(root)
            self.assertEqual((settings['window_frames'],settings['min_valid'],settings['other']),(10,6,9))
            before=(root/board.SETTINGS).read_bytes()
            with self.assertRaises(ValueError):board.set_filter(5,6,root)
            self.assertEqual((root/board.SETTINGS).read_bytes(),before)

    def test_normal_debug_commands_share_saved_and_override_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);board.set_filter(10,6,root)
            for operation in ('normal','debug'):
                args=SimpleNamespace(operation=operation,frames=None,mode='real',min_level=None,
                                     window_frames=None,min_valid=None)
                command,_,_=board.run_arguments(args,root)
                parsed=normal.parse_args(command[2:] if operation=='normal' else
                    [x for x in command[2:] if x!='--angle-filter'])
                self.assertEqual((parsed.window_frames,parsed.min_valid),(10,6))
                args.window_frames,args.min_valid=8,5
                command,_,_=board.run_arguments(args,root)
                self.assertEqual(command[command.index('--window-frames')+1],'8')
                self.assertEqual(command[command.index('--min-valid')+1],'5')
                self.assertEqual(board.get_settings(root)['window_frames'],10)

    def test_normal_and_debug_worker_construct_configured_real_filter(self):
        for module in (normal,buffered):
            args=SimpleNamespace(worker_cpu=1,lock_file='unused',library='unused',min_level=1000,
                                 angle_filter=True,window_frames=7,min_valid=4)
            conn=Mock()
            session_name='normal_session' if module is normal else 'buffered_session'
            with patch.dict(sys.modules,{'pynq':SimpleNamespace(MMIO=Mock())}), \
                 patch.object(module,'pinned',return_value=contextlib.nullcontext()), \
                 patch.object(module,'single_owner',return_value=contextlib.nullcontext()), \
                 patch.object(module,'Solver'),patch.object(VolumeClient,'identify'), \
                 patch.object(module,session_name) as session, \
                 patch.object(module.os,'sched_getaffinity',return_value={1},create=True):
                module.worker_main(conn,Mock(),Mock(),args,0,4096)
                session.assert_called_once()
                client=session.call_args[0][3]
                self.assertEqual((client.angle_filter.window_frames,client.angle_filter.min_valid),(7,4))

    def test_filter_command_is_locked_and_read_does_not_require_board(self):
        out=io.StringIO()
        with patch.object(board,'get_settings',return_value=dict(window_frames=10,min_valid=6)), \
             patch.object(board,'load_api') as api,contextlib.redirect_stdout(out):
            self.assertEqual(board.main(['filter']),0)
            api.assert_not_called()
        self.assertIn('WINDOW_FRAMES=10 MIN_VALID=6',out.getvalue())
        with patch.object(board.os,'geteuid',return_value=0,create=True), \
             patch.object(board,'single_owner',side_effect=RuntimeError('busy')), \
             patch.object(board,'set_filter') as setter,contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(board.main(['filter','10','6']),1)
            setter.assert_not_called()

    def test_bad_cli_counts_stop_before_board_access(self):
        base=['--hwh','unused','--output','unused','--min-level','1000']
        with contextlib.redirect_stderr(io.StringIO()):
            for parse in (normal.parse_args,buffered.main):
                with self.assertRaises(SystemExit):parse(base+['--window-frames','5','--min-valid','6'])


if __name__=='__main__':unittest.main()
