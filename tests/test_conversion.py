"""Exercise the real CLI, ExifTool, JPEG/HEIC encoders and video decoder."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from lxml import etree
from PIL import Image
from pillow_heif import register_heif_opener

from tests.generate_samples import CAPTURE_TIME, CONTENT_ID, generate_samples, run


ROOT = Path(__file__).resolve().parents[1]
APP_EXECUTABLE = None
SOURCE_FILES = ("motionphoto2.py", "mac_gui.py", "Muxer.py", "SamsungTags.py", "constants.py", "utils.py")
NS = {
    "g": "http://ns.google.com/photos/1.0/camera/",
    "c": "http://ns.google.com/photos/1.0/container/",
    "i": "http://ns.google.com/photos/1.0/container/item/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
}


def snapshot(directory):
    return {
        str(path.relative_to(directory)): (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
        for path in directory.rglob("*") if path.is_file()
    }


class ConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory(prefix="motionphoto2-fixtures-")
        cls.addClassCleanup(cls.shared.cleanup)
        cls.samples = generate_samples(Path(cls.shared.name) / "samples")
        cls.app = None
        if APP_EXECUTABLE:
            # Never let the legacy settings writer modify the signed original.
            bundle = APP_EXECUTABLE.parent.parent.parent
            copied = Path(cls.shared.name) / bundle.name
            shutil.copytree(bundle, copied, symlinks=True)
            cls.app = copied / APP_EXECUTABLE.relative_to(bundle)
        register_heif_opener()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="motionphoto2-中文 空格-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.source = self.work / "原始 照片"
        self.source.mkdir()
        self.output = self.work / "输出 照片"
        # The legacy CLI writes settings next to __file__. Run an exact source
        # copy so tests cannot overwrite the user's motionphoto2.json.
        code = self.work / "code"
        code.mkdir()
        for name in SOURCE_FILES:
            shutil.copy2(ROOT / name, code / name)
        self.command = [str(self.app), "--cli"] if self.app else [sys.executable, str(code / "mac_gui.py"), "--cli"]
        self.env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")

    def copy_sample(self, suffix, name):
        target = self.source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.samples / f"PHOTO.{suffix}", target)
        return target

    def cli(self, *args, success=True):
        result = subprocess.run(
            self.command + [str(arg) for arg in args], cwd=self.work,
            env=self.env, capture_output=True, text=True, encoding="utf-8", timeout=90,
        )
        detail = result.stdout + result.stderr
        if success:
            self.assertEqual(result.returncode, 0, detail)
            self.assertNotIn("[ERROR]", detail)
        else:
            self.assertNotEqual(result.returncode, 0, detail)
        return detail

    def directory_cli(self, *args):
        return self.cli("--input-directory", self.source, "--output-directory", self.output, *args)

    def assert_motion_photo(self, output, original, video):
        self.assertTrue(output.is_file(), f"No output: {output}")
        self.assertGreater(output.stat().st_size, original.stat().st_size)
        metadata = json.loads(run(["exiftool", "-j", "-n", "-G1", output]))[0]
        self.assertEqual(metadata["XMP-GCamera:MotionPhoto"], 1)
        self.assertEqual(metadata["ExifIFD:DateTimeOriginal"], CAPTURE_TIME)
        self.assertEqual(metadata["IFD0:Make"], "Apple")
        self.assertEqual(metadata["IFD0:Model"], "MotionPhoto2 synthetic fixture")
        self.assertEqual(metadata["Apple:ContentIdentifier"], CONTENT_ID)
        self.assertAlmostEqual(metadata["GPS:GPSLatitude"], 1)
        self.assertAlmostEqual(metadata["GPS:GPSLongitude"], 2)
        self.assertEqual(metadata["XMP-dc:Description"], "Synthetic regression fixture")
        self.assertAlmostEqual(output.stat().st_mtime, original.stat().st_mtime, places=3)

        # Check the XMP directory against bytes, independently of production
        # extraction helpers; a mere copy or a bogus offset must fail.
        xmp = etree.fromstring(run(["exiftool", "-b", "-XMP", output]))
        items = xmp.findall(".//c:Item", NS)
        self.assertEqual(len(items), 2)
        motion = next(item for item in items if item.get(f"{{{NS['i']}}}Semantic") == "MotionPhoto")
        length = int(motion.get(f"{{{NS['i']}}}Length"))
        data = output.read_bytes()
        video_bytes = video.read_bytes()
        self.assertGreaterEqual(length, len(video_bytes))
        self.assertLess(length, len(data))
        self.assertTrue(data[-length:].startswith(video_bytes), "XMP video offset does not point to the source video")

        # JPEG exposes the exact SEF payload. HEIC exposes the mpvd content,
        # which includes the unchanged video followed by the sefd trailer.
        if original.suffix.lower() in (".heic", ".heif"):
            extracted = run(["exiftool", "-b", "-MotionPhotoVideo", output])
            self.assertEqual(extracted, data[-length:])
            self.assertTrue(extracted.startswith(video_bytes))
        else:
            extracted = run(["exiftool", "-b", "-EmbeddedVideoFile", output])
            self.assertEqual(extracted, video_bytes)
        extracted_path = self.work / "extracted.mov"
        extracted_path.write_bytes(extracted)
        info = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", extracted_path]))
        stream = next(stream for stream in info["streams"] if stream["codec_type"] == "video")
        self.assertEqual((stream["width"], stream["height"]), (96, 64))
        run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", extracted_path, "-f", "null", "-"])
        with Image.open(original) as before, Image.open(output) as after:
            self.assertEqual(after.size, before.size)
            self.assertEqual(after.convert("RGB").tobytes(), before.convert("RGB").tobytes())
        self.assertFalse(list(self.output.rglob("*.XMP")))
        self.assertFalse(list(self.output.rglob("*.XMP.*")))

    def test_jpeg_and_heic_with_mov_and_mp4(self):
        for image_type in ("JPG", "HEIC"):
            for video_type in ("MOV", "MP4"):
                with self.subTest(image=image_type, video=video_type):
                    name = f"{image_type}-{video_type}"
                    image = self.copy_sample(image_type, f"{name}.{image_type}")
                    video = self.copy_sample(video_type, f"{name}.{video_type}")
                    before = snapshot(self.source)
                    self.directory_cli()
                    self.assert_motion_photo(self.output / image.name, image, video)
                    self.assertEqual(snapshot(self.source), before)

    def test_single_pair_with_explicit_output_file(self):
        image = self.copy_sample("JPG", "still.jpg")
        video = self.copy_sample("MOV", "clip.mov")
        self.output.mkdir()
        output = self.output / "选择的结果.jpg"
        before = snapshot(self.source)
        self.cli("--input-image", image, "--input-video", video, "--output-file", output)
        self.assert_motion_photo(output, image, video)
        self.assertEqual(snapshot(self.source), before)

    def test_exif_pairing_uses_identifier_not_filename(self):
        for suffix in ("JPG", "HEIC"):
            with self.subTest(image=suffix):
                image = self.copy_sample(suffix, f"{suffix}/still.{suffix}")
                video = self.copy_sample("MOV", f"{suffix}/renamed.mov")
                decoy = self.copy_sample("MP4", f"{suffix}/still.mp4")
                before = snapshot(self.source)
                self.directory_cli("--recursive", "--exif-match", "--copy-unmuxed")
                self.assert_motion_photo(self.output / suffix / image.name, image, video)
                self.assertEqual((self.output / suffix / decoy.name).read_bytes(), decoy.read_bytes())
                self.assertFalse((self.output / suffix / video.name).exists())
                self.assertEqual(snapshot(self.source), before)

    def test_recursive_folders_and_copy_unmatched_files(self):
        image = self.copy_sample("HEIC", "旅行 2024/IMG_001.HEIC")
        video = self.copy_sample("MOV", "旅行 2024/IMG_001.MOV")
        plain = self.copy_sample("JPG", "旅行 2024/普通照片.jpg")
        orphan = self.copy_sample("MOV", "其他/无配对.mov")
        note = self.source / "说明.txt"
        note.write_text("这是合成样本，不含私人照片。", encoding="utf-8")
        before = snapshot(self.source)
        self.directory_cli("--recursive", "--copy-unmuxed")
        self.assert_motion_photo(self.output / image.relative_to(self.source), image, video)
        for path in (plain, orphan, note):
            self.assertEqual((self.output / path.relative_to(self.source)).read_bytes(), path.read_bytes())
        self.assertEqual(snapshot(self.source), before)
        self.assertFalse((self.output / video.relative_to(self.source)).exists())

    def test_incremental_mode_leaves_existing_result_untouched(self):
        image = self.copy_sample("JPG", "PHOTO.JPG")
        self.copy_sample("MOV", "PHOTO.MOV")
        self.directory_cli()
        output = self.output / image.name
        os.utime(output, (1234567890, 1234567890))
        before = snapshot(self.output)
        text = self.directory_cli("--incremental-mode")
        self.assertIn("already a motion photo", text)
        self.assertEqual(snapshot(self.output), before)

    def test_existing_motion_photo_is_copied_without_remuxing(self):
        image = self.copy_sample("JPG", "PHOTO.JPG")
        self.copy_sample("MOV", "PHOTO.MOV")
        self.directory_cli()
        shutil.copy2(self.output / image.name, image)
        self.output = self.work / "再次输出"
        before = snapshot(self.source)
        text = self.directory_cli("--copy-unmuxed")
        self.assertIn("already a motion photo", text)
        self.assertEqual((self.output / image.name).read_bytes(), image.read_bytes())
        self.assertEqual(snapshot(self.source), before)

    def test_empty_directory_in_exif_mode(self):
        self.directory_cli("--exif-match", "--copy-unmuxed")
        self.assertEqual(list(self.output.iterdir()), [])

    @unittest.expectedFailure
    def test_all_xmp_description_blocks_are_preserved(self):
        # Known baseline defect: Muxer.merge_xmp reads only the first
        # rdf:Description. Stage 0 is explicitly not allowed to change it.
        # Remove expectedFailure when implementing docs/KNOWN_ISSUES.md XMP-1.
        image = self.copy_sample("JPG", "PHOTO.JPG")
        self.copy_sample("MOV", "PHOTO.MOV")
        self.directory_cli()
        metadata = json.loads(run(["exiftool", "-j", "-Rating", self.output / image.name]))[0]
        self.assertEqual(metadata.get("Rating"), 4)

    def test_unpaired_image_in_exif_mode_is_copied(self):
        image = self.copy_sample("HEIC", "lonely.heic")
        self.directory_cli("--exif-match", "--copy-unmuxed")
        self.assertEqual((self.output / image.name).read_bytes(), image.read_bytes())

    def test_unpaired_video_in_exif_mode_is_copied(self):
        video = self.copy_sample("MOV", "lonely.mov")
        self.directory_cli("--exif-match", "--copy-unmuxed")
        self.assertEqual((self.output / video.name).read_bytes(), video.read_bytes())

    def test_invalid_option_combination_fails_without_changing_sources(self):
        self.copy_sample("JPG", "PHOTO.JPG")
        self.copy_sample("MOV", "PHOTO.MOV")
        before = snapshot(self.source)
        self.cli("--input-directory", self.source, "--output-directory", self.output, "--overwrite", success=False)
        self.assertEqual(snapshot(self.source), before)
        self.assertFalse(self.output.exists())
