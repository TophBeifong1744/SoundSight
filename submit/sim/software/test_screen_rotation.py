"""Screen pixel/touch inverse mapping; no MMIO, downloads or motion."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'software/screen'))
import ui
import backend
import product


class RotationTests(unittest.TestCase):
    def test_legacy_pillow_renders_all_pages_and_rotated_navigation(self):
        real_draw = ImageDraw.Draw
        measured = []

        class LegacyDraw:
            # Expose the pre-textbbox API while retaining real pixel rendering.
            def __init__(self, *args, **kwargs):
                self.draw = real_draw(*args, **kwargs)

            def __getattr__(self, name):
                if name == 'textbbox':
                    raise AttributeError(name)
                return getattr(self.draw, name)

            def textsize(self, value, font=None):
                measured.append(value)
                bbox = getattr(self.draw, 'textbbox', None)
                if callable(bbox):
                    box = bbox((0, 0), value, font=font)
                    return box[2], box[3]
                return self.draw.textsize(value, font=font)

        with tempfile.TemporaryDirectory() as folder:
            b = backend.Backend(Path(folder), control=False, motion=False, demo=True)
            screen = ui.UI(b)
            with patch.object(ImageDraw, 'Draw', LegacyDraw):
                for page, x in [('HOME', 100), ('USERS', 300),
                                ('SETTINGS', 500), ('DIAGNOSTICS', 700)]:
                    frame = ui.rotate_frame(screen.render(), 180)
                    self.assertEqual(frame.size, (800, 480))
                    screen.touch(ui.rotate_touch([(799-x, 479-115)], 180))
                    screen.touch([])
                    self.assertEqual(screen.page, page)
                screen.render()
            self.assertTrue(measured)
            self.assertEqual(screen.axes, 'off')
            self.assertFalse(b.busy)

    def test_full_frame_exact_permutation_without_channel_swap(self):
        pixels = np.arange(480*800*3, dtype=np.uint32).reshape(480,800,3).astype(np.uint8)
        frame = Image.fromarray(pixels)
        flipped = ui.rotate_frame(frame, 180)
        np.testing.assert_array_equal(np.array(flipped), pixels[::-1,::-1,:])
        np.testing.assert_array_equal(np.array(ui.rotate_frame(flipped,180)), pixels)
        self.assertIs(ui.rotate_frame(frame,0),frame)

    def test_touch_inverse_corners_and_interior(self):
        physical = [(0,0),(799,0),(0,479),(799,479),(211,307)]
        logical = [(799,479),(0,479),(799,0),(0,0),(588,172)]
        self.assertEqual(ui.rotate_touch(physical,180),logical)
        self.assertEqual(ui.rotate_touch(logical,180),physical)
        self.assertEqual(ui.rotate_touch(physical,0),physical)

    def test_release_no_update_and_invalid_coordinates(self):
        self.assertIsNone(ui.rotate_touch(None,180))
        self.assertEqual(ui.rotate_touch([],180),[])
        for point in ((800,0),(-1,0),(0,480),(0,-1)):
            with self.assertRaises(ValueError): ui.rotate_touch([point],180)

    def test_default_and_persistent_override(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.assertEqual(ui.screen_rotation(root),180)
            config=root/'screen-orientation.local.json'
            config.write_text(json.dumps({'rotation':0}))
            self.assertEqual(ui.screen_rotation(root),0)
            self.assertEqual(ui.screen_rotation(root,180),180)
            self.assertIn(config.name,product.fingerprints(root))
            product.save_mode(root,'SPEAKER')
            self.assertEqual(ui.screen_rotation(root),0)

    def test_invalid_config_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for value in ([],{}, {'rotation':90},{'rotation':True},{'rotation':'180'}):
                (root/'screen-orientation.local.json').write_text(json.dumps(value))
                with self.assertRaises(ValueError): ui.screen_rotation(root)

    def test_rotated_navigation_hits_original_button_without_start(self):
        with tempfile.TemporaryDirectory() as folder:
            b=backend.Backend(Path(folder),control=False,motion=False,demo=True)
            screen=ui.UI(b)
            screen.render()
            # Top navigation SETTINGS logical point; physical point on rotated LCD.
            screen.touch(ui.rotate_touch([(799-500,479-115)],180))
            self.assertEqual(screen.page,'SETTINGS')
            self.assertEqual(screen.axes,'off')
            self.assertFalse(b.busy)


if __name__ == '__main__': unittest.main(verbosity=2)
