"""Synthetic private profiles and touch events only; no board or real users."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'software/ps'), str(ROOT/'software/screen'),
               str(ROOT/'software/tetra3d/linux')]
import speaker_delete as deletion
import speaker_targets as targets
from speaker_permission import settings, load_settings
import backend
import ui


class DeleteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.profile('user1'); self.profile('user2')
        targets.atomic_json(self.root/targets.SELECTOR, dict(schema=1, target_id='user1'))
        targets.atomic_json(self.root/'speaker-follow.local.json', settings(.65, 10))
        (self.root/'logs').mkdir()
        (self.root/'logs/recording.bin').write_bytes(b'keep audio')

    def profile(self, name):
        p = targets.profile_path(self.root, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        targets.atomic_json(p, dict(target_id=name, template=[1, 0]))
        return p

    def erase(self, name):
        token = deletion.preview(self.root, name)['token']
        return deletion.delete(self.root, name, name, token)

    def test_active_delete_clears_gate_and_prevents_default_fallback(self):
        other = targets.profile_path(self.root, 'user2').read_bytes()
        self.assertTrue(self.erase('user1')['active_target_cleared'])
        self.assertFalse(targets.profile_path(self.root, 'user1').parent.exists())
        self.assertIsNone(load_settings(self.root)['threshold'])
        core = self.root/'software/ps/speaker_core'
        with self.assertRaisesRegex(ValueError, 'NO_ACTIVE_TARGET'):
            targets.selected_config(core, {'target_id':'P01'}, {})
        self.assertEqual(targets.profile_path(self.root, 'user2').read_bytes(), other)
        self.assertEqual((self.root/'logs/recording.bin').read_bytes(), b'keep audio')

    def test_inactive_delete_preserves_selection_and_threshold(self):
        before = [(self.root/n).read_bytes() for n in (targets.SELECTOR, 'speaker-follow.local.json')]
        self.assertFalse(self.erase('user2')['active_target_cleared'])
        self.assertEqual(before, [(self.root/n).read_bytes() for n in (targets.SELECTOR, 'speaker-follow.local.json')])

    def test_wrong_confirmation_and_changed_profile_delete_nothing(self):
        token = deletion.preview(self.root, 'user1')['token']
        with self.assertRaisesRegex(ValueError, 'CONFIRM_TARGET'):
            deletion.delete(self.root, 'user1', 'user2', token)
        targets.atomic_json(targets.profile_path(self.root, 'user1'), dict(target_id='user1', template=[0,1]))
        with self.assertRaisesRegex(ValueError, 'PROFILE_CHANGED'):
            deletion.delete(self.root, 'user1', 'user1', token)
        self.assertTrue(targets.profile_path(self.root, 'user1').exists())
        self.assertEqual(load_settings(self.root)['threshold'], .65)

    def test_paths_builtins_unknown_files_and_id_mismatch_rejected(self):
        for name in ('../user1','user1/x','P01','p01','P02-v1','missing'):
            with self.assertRaises((ValueError, FileNotFoundError)):
                deletion.preview(self.root, name)
        extra = targets.profile_path(self.root,'user1').parent/'do-not-delete.txt'
        extra.write_text('private')
        with self.assertRaisesRegex(ValueError, 'UNEXPECTED_PROFILE_CONTENT'):
            self.erase('user1')
        self.assertTrue(extra.exists())
        targets.atomic_json(targets.profile_path(self.root,'user2'), dict(target_id='someone_else'))
        with self.assertRaisesRegex(ValueError, 'PROFILE_TARGET_MISMATCH'):
            self.erase('user2')

    def test_legacy_p02_maps_only_to_exact_directory(self):
        p=self.profile('P02')
        (p.parent/'evaluation.json').write_text('{}')
        self.erase('P02')
        self.assertFalse(p.parent.exists())
        self.assertTrue(targets.profile_path(self.root,'user1').exists())

    def test_config_write_failure_keeps_profile(self):
        token=deletion.preview(self.root,'user1')['token']
        with patch.object(deletion, 'atomic_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                deletion.delete(self.root,'user1','user1',token)
        self.assertTrue(targets.profile_path(self.root,'user1').exists())
        self.assertIsNone(load_settings(self.root)['threshold'])

    def test_symlink_refused_before_any_delete(self):
        # Simulate an OS-reported link on Windows without symlink privileges.
        victim=targets.profile_path(self.root,'user1').resolve()
        original=type(victim).is_symlink
        with patch.object(type(victim),'is_symlink',lambda p: p==victim or original(p)):
            with self.assertRaisesRegex(ValueError,'REDIRECTED'):
                self.erase('user1')
        self.assertTrue(victim.exists())

    def screen(self):
        b=backend.Backend(self.root,control=True,motion=True)
        u=ui.UI(b);u.page='USERS';u.user_index=b.cache['profiles'].index('user1')
        return b,u

    def test_cancel_stop_and_repeated_touch_do_not_delete(self):
        b,u=self.screen()
        with patch.object(b,'_launch') as launch:
            u.render()
            u.touch(ui.rotate_touch([(799-100,479-360)],180))
            self.assertEqual(u.modal,'DELETE')
            u.render()
            # A held/dragged finger cannot also confirm.
            u.touch(ui.rotate_touch([(799-500,479-350)],180))
            launch.assert_not_called()
            u.touch([])
            u.action('CANCEL'); self.assertIsNone(u.modal)
            u.action('USER_DELETE');u.action('STOP')
            self.assertIsNone(u.modal)
            launch.assert_not_called()
        self.assertTrue(targets.profile_path(self.root,'user1').exists())

    def test_confirmation_pins_displayed_name_not_new_list_index(self):
        b,u=self.screen()
        u.action('USER_DELETE')
        u.user_index=b.cache['profiles'].index('user2')
        with patch.object(b,'_launch') as launch:
            u.render();u.action('DELETE_CONFIRM')
            args,operation=launch.call_args.args
            self.assertEqual(operation,'DELETE')
            self.assertEqual(args[:4],['speaker-delete','user1','--confirm-target','user1'])
            self.assertEqual(u.axes,'off')

    def test_changed_profile_and_running_owner_block_confirmation(self):
        b,u=self.screen();u.action('USER_DELETE')
        self.profile('user1')
        targets.profile_path(self.root,'user1').write_text('{"target_id":"user1","changed":true}')
        with patch.object(b,'_launch') as launch:
            u.action('DELETE_CONFIRM');launch.assert_not_called()
            self.assertIn('changed',u.message)
        b.state='RUNNING'
        with self.assertRaisesRegex(RuntimeError,'STOP'):
            b.deletion_preview('user2')

    def test_cli_requires_confirmation_and_owner_lock(self):
        import board_3d
        with self.assertRaises(SystemExit):
            board_3d.parser().parse_args(['speaker-delete','user1'])
        token=deletion.preview(self.root,'user1')['token']
        with patch.object(board_3d,'ROOT',self.root), patch.object(board_3d,'single_owner',side_effect=RuntimeError('owner busy')):
            self.assertNotEqual(board_3d.main(['speaker-delete','user1','--confirm-target','user1','--expected-token',token]),0)
        self.assertTrue(targets.profile_path(self.root,'user1').exists())


if __name__=='__main__':unittest.main(verbosity=2)
