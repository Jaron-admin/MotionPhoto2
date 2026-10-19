"""Generate tiny, non-personal JPEG/HEIC + MOV/MP4 fixtures locally.

These are synthetic media with pairing metadata, not camera-produced Live
Photos: they do not contain Apple's timed still-image metadata track or HDR.
"""

import argparse
import json
import os
from pathlib import Path
import struct
import subprocess

from PIL import Image
from pillow_heif import register_heif_opener


CONTENT_ID = "00000000-0000-4000-8000-000000000001"
OTHER_ID = "00000000-0000-4000-8000-000000000002"
CAPTURE_TIME = "2024:01:02 03:04:05"
FILE_TIME = 1704164645


def run(command):
    result = subprocess.run(
        [str(arg) for arg in command], capture_output=True, timeout=60
    )
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {command}\n"
            + result.stderr.decode("utf-8", errors="replace")
        )
    return result.stdout


def apple_maker_note(identifier):
    """Minimal Apple IFD, tag 0x0011 (ContentIdentifier), no real camera data.

    Layout follows ExifTool's Apple.pm / MakerNotes.pm: a 14-byte Apple
    header, one 12-byte ASCII IFD entry and a zero next-IFD offset. String
    offsets are relative to the beginning of the maker note.
    """
    value = identifier.encode("ascii") + b"\0"
    return (
        b"Apple iOS\0\0\1MM"
        + struct.pack(">H", 1)
        + struct.pack(">HHII", 0x0011, 2, len(value), 32)
        + b"\0" * 4
        + value
    )


def generate_samples(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise ValueError("测试样本目录必须为空，避免覆盖已有文件。")

    register_heif_opener()
    image = Image.new("RGB", (96, 64), (240, 120, 40))
    exif = Image.Exif()
    exif[0x010F] = "Apple"
    exif[0x0110] = "MotionPhoto2 synthetic fixture"
    exif[0x8769] = {0x927C: apple_maker_note(CONTENT_ID)}
    for suffix in ("JPG", "HEIC"):
        path = directory / f"PHOTO.{suffix}"
        image.save(path, exif=exif, quality=80)
        run([
            "exiftool", "-overwrite_original", f"-EXIF:DateTimeOriginal={CAPTURE_TIME}",
            f"-EXIF:CreateDate={CAPTURE_TIME}", "-GPSLatitude=1", "-GPSLatitudeRef=N",
            "-GPSLongitude=2", "-GPSLongitudeRef=E",
            "-XMP-dc:Description=Synthetic regression fixture", "-XMP-xmp:Rating=4", path,
        ])
        metadata = json.loads(run(["exiftool", "-j", "-ContentIdentifier", path]))[0]
        if metadata.get("ContentIdentifier") != CONTENT_ID:
            raise RuntimeError(f"样本配对标识写入失败：{path}")

    for suffix, identifier in (("MOV", CONTENT_ID), ("MP4", OTHER_ID)):
        path = directory / f"PHOTO.{suffix}"
        run([
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
            "-f", "lavfi", "-i", "testsrc2=size=96x64:rate=6", "-t", "0.5",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-threads", "1", path,
        ])
        run(["exiftool", "-overwrite_original", f"-Keys:ContentIdentifier={identifier}", path])

    for path in directory.iterdir():
        os.utime(path, (FILE_TIME, FILE_TIME))
    return directory


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成不含个人信息的小型转换测试样本")
    parser.add_argument("directory", type=Path, help="新目录或空目录")
    args = parser.parse_args()
    print(generate_samples(args.directory).resolve())
