import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tests.generate_samples import generate_samples, run, FILE_TIME
from tests.reverse_samples import motion_photo


class ReverseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory(prefix='reverse-fixtures-')
        cls.addClassCleanup(cls.shared.cleanup)
        cls.samples = generate_samples(Path(cls.shared.name)/'samples')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='实况 安全-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / '输入'
        self.source.mkdir()
        self.output = self.root / '输出'

    def fixture(self, suffix='JPG', legacy=False, name='照片', **kwargs):
        return motion_photo(self.samples/f'PHOTO.{suffix}', self.samples/'PHOTO.MOV',
                            self.source/f'{name}.{suffix}', legacy=legacy, **kwargs)

    def test_new_and_legacy_jpeg_and_heic_preserve_source_and_metadata(self):
        from reverse.convert import convert_file
        for suffix, legacy in [('JPG', False), ('JPG', True), ('HEIC', False)]:
            with self.subTest(suffix=suffix, legacy=legacy):
                source = self.fixture(suffix, legacy, name=f'{suffix}{legacy}')
                os.utime(source, (FILE_TIME, FILE_TIME))
                original = source.read_bytes()
                result = convert_file(source, self.output)
                self.assertEqual(result.status, 'converted', result.message)
                still, movie = result.paths
                meta = json.loads(run(['exiftool', '-j', '-n', still]))[0]
                self.assertEqual(meta['Description'], 'Keep second description')
                self.assertNotIn('MotionPhoto', meta)
                self.assertNotIn('MicroVideo', meta)
                self.assertEqual(meta['ContentIdentifier'], json.loads(run(['exiftool', '-j', movie]))[0]['ContentIdentifier'])
                self.assertEqual(source.read_bytes(), original)
                self.assertEqual(source.stat().st_mtime, FILE_TIME)
                self.assertEqual(still.stat().st_mtime, FILE_TIME)
                self.assertEqual(movie.stat().st_mtime, FILE_TIME)

    def test_invalid_offset_is_error_and_plain_photo_is_skipped(self):
        from reverse.convert import convert_file
        malformed = self.fixture(offset_adjust=99)
        result = convert_file(malformed, self.output)
        self.assertEqual(result.status, 'error')
        plain = convert_file(self.samples/'PHOTO.JPG', self.output)
        self.assertEqual(plain.status, 'plain')
        self.assertFalse(list(self.output.glob('*')) if self.output.exists() else [])

    def test_collision_skips_whole_pair_and_does_not_delete_existing(self):
        from reverse.convert import convert_file
        source = self.fixture()
        self.output.mkdir()
        existing = self.output/(source.stem+'.MOV')
        existing.write_bytes(b'keep existing video')
        result = convert_file(source, self.output)
        self.assertEqual(result.status, 'skipped')
        self.assertEqual(existing.read_bytes(), b'keep existing video')
        self.assertFalse((self.output/source.name).exists())

    def test_second_publish_failure_rolls_back_only_new_first_file(self):
        from reverse.convert import convert_file
        source = self.fixture()
        link = os.link
        def fail_second(src, dst, **kwargs):
            if str(dst).endswith('.MOV'):
                Path(dst).write_bytes(b'concurrent output')
                raise FileExistsError(dst)
            return link(src, dst, **kwargs)
        with patch('reverse.convert.os.link', side_effect=fail_second):
            result = convert_file(source, self.output)
        self.assertEqual(result.status, 'skipped')
        self.assertEqual((self.output/(source.stem+'.MOV')).read_bytes(), b'concurrent output')
        self.assertFalse((self.output/source.name).exists())
        self.assertEqual(len(list(self.output.iterdir())), 1)

    def test_output_inside_input_and_symlink_escape_are_rejected(self):
        from reverse.convert import convert_directory
        self.fixture()
        for output in (self.source, self.source/'nested'):
            with self.assertRaises(ValueError):
                list(convert_directory(self.source, output, recursive=True))
        self.output.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(ValueError):
            list(convert_directory(self.source, self.output, recursive=True))

    def test_batch_continues_after_error(self):
        from reverse.convert import convert_directory
        self.fixture(name='a-bad', offset_adjust=99)
        self.fixture(name='b-good')
        results = list(convert_directory(self.source, self.output))
        self.assertEqual([r.status for r in results], ['error', 'converted'])

    def test_source_named_still_does_not_collide_with_staging_files(self):
        from reverse.convert import convert_file
        result = convert_file(self.fixture(name='still'), self.output)
        self.assertEqual(result.status, 'converted', result.message)

    def test_duplicate_directory_and_disabled_flag_are_not_fallbacks(self):
        from reverse.convert import convert_file
        source = self.fixture()
        data = source.read_bytes()
        xml = run(['exiftool', '-b', '-XMP', source])
        start = xml.index(b'<d:Directory>')
        end = xml.index(b'</d:Directory>') + len(b'</d:Directory>')
        modified = xml[:end] + xml[start:end] + xml[end:]
        # Rewrite XMP on the full Motion Photo through ExifTool; appended media is retained.
        path = self.root/'duplicate.xmp'
        path.write_bytes(modified)
        run(['exiftool', '-overwrite_original', f'-XMP<={path}', source])
        self.assertEqual(convert_file(source, self.output).status, 'error')
        path.write_bytes(xml.replace(b'c:MotionPhoto="1"', b'c:MotionPhoto="0"'))
        run(['exiftool', '-overwrite_original', f'-XMP<={path}', source])
        result = convert_file(source, self.output)
        self.assertEqual(result.status, 'plain', result.message)

    def test_nested_output_symlink_cannot_redirect_into_input(self):
        from reverse.convert import convert_directory
        sub = self.source/'sub'
        sub.mkdir()
        source = self.fixture()
        source.rename(sub/source.name)
        self.output.mkdir()
        (self.output/'sub').symlink_to(self.source, target_is_directory=True)
        results = list(convert_directory(self.source, self.output, recursive=True))
        self.assertEqual(results[0].status, 'error')
        self.assertFalse((self.source/'照片.MOV').exists())

    def test_cancellation_during_second_publish_removes_temporary_pair(self):
        from reverse.convert import convert_file
        source = self.fixture()
        link = os.link
        def interrupt_second(src, dst, **kwargs):
            if str(dst).endswith('.MOV'):
                raise KeyboardInterrupt
            return link(src, dst, **kwargs)
        with patch('reverse.convert.os.link', side_effect=interrupt_second), self.assertRaises(KeyboardInterrupt):
            convert_file(source, self.output)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_legacy_offset_cannot_recover_corrupt_current_directory(self):
        from reverse.convert import convert_file
        source = self.fixture(offset_adjust=10)
        run(['exiftool', '-overwrite_original', '-XMP-GCamera:MicroVideo=1',
             f'-XMP-GCamera:MicroVideoOffset={(self.samples/"PHOTO.MOV").stat().st_size}', source])
        self.assertEqual(convert_file(source, self.output).status, 'error')
