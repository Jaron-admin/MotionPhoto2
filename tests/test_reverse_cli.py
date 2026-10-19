import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from tests.generate_samples import generate_samples
from tests.reverse_samples import motion_photo
from tests import test_conversion

ROOT = Path(__file__).resolve().parents[1]


class ReverseCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='reverse-cli-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.samples = generate_samples(cls.root/'samples')
        cls.command = [sys.executable, str(ROOT/'mac_gui.py'), '--cli']
        if test_conversion.APP_EXECUTABLE:
            app = test_conversion.APP_EXECUTABLE
            copied = cls.root/app.parent.parent.parent.name
            shutil.copytree(app.parent.parent.parent, copied, symlinks=True)
            cls.command = [str(copied/app.relative_to(app.parent.parent.parent)), '--cli']

    def fixture(self, name):
        folder = self.root/name
        folder.mkdir()
        return motion_photo(self.samples/'PHOTO.JPG', self.samples/'PHOTO.MOV', folder/'照片.JPG')

    def cli(self, *args):
        return subprocess.run(self.command + ['--direction', 'motion-to-live', *map(str,args)],
                              capture_output=True, text=True, timeout=90)

    def test_reverse_single_and_default_directory(self):
        source = self.fixture('single')
        result = self.cli('--input-image', source)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        target = source.parent.with_name('single_实况照片')
        self.assertTrue((target/'照片.JPG').exists())
        self.assertTrue((target/'照片.MOV').exists())
        self.assertIn('converted', result.stdout)

    def test_reverse_batch_exit_code_reports_partial_failure(self):
        source = self.fixture('batch')
        motion_photo(self.samples/'PHOTO.JPG', self.samples/'PHOTO.MOV', source.parent/'bad.JPG', offset_adjust=50)
        result = self.cli('--input-directory', source.parent)
        self.assertEqual(result.returncode, 1, result.stdout+result.stderr)
        self.assertIn('converted', result.stdout)
        self.assertIn('error', result.stdout)

    def test_reverse_rejects_forward_destructive_options(self):
        source = self.fixture('invalid')
        result = self.cli('--input-image', source, '--delete-video')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(source.parent.with_name('invalid_实况照片').exists())

    def test_gui_filters_forward_options_and_keeps_custom_output(self):
        from mac_gui import conversion_arguments, updated_output, DEFAULT_SETTINGS
        settings = dict(DEFAULT_SETTINGS, direction='motion-to-live', input_directory='/input', output_directory='/output',
                        exif_match=True, copy_unmuxed=True, incremental_mode=True, recursive=True)
        args = conversion_arguments(settings)
        self.assertIn('motion-to-live', args)
        self.assertIn('--recursive', args)
        for option in ('--exif-match', '--copy-unmuxed', '--incremental-mode'):
            self.assertNotIn(option, args)
        self.assertEqual(updated_output('/input', '/custom', 'motion-to-live', False), '/custom')
        self.assertEqual(updated_output('/input', '/old', 'motion-to-live', True), '/input_实况照片')

    def test_reverse_log_categories_reach_gui_statistics(self):
        from mac_gui import translate
        for status in ('converted', 'plain', 'skipped', 'unsupported', 'error'):
            line = '[REVERSE] ' + json.dumps({'status': status, 'name': '照片.JPG', 'message': '测试'})
            kind, message = translate(line, True)
            self.assertEqual(kind, status)
            self.assertIn('照片.JPG', message)

    def test_existing_settings_keep_user_selected_output_after_upgrade(self):
        import mac_gui
        from unittest.mock import patch
        file = self.root/'previous-settings.json'
        file.write_text(json.dumps({'input_directory': '/input', 'output_directory': '/custom'}))
        with patch.object(mac_gui, 'SETTINGS_FILE', file):
            settings = mac_gui.load_settings()
        self.assertFalse(settings['output_automatic'])
        self.assertEqual(mac_gui.updated_output('/input', settings['output_directory'], 'motion-to-live',
                                              settings['output_automatic']), '/custom')
