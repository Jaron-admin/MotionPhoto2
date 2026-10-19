"""Lossless metadata edits using ExifTool; no Apple framework dependency."""
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import uuid


def exiftool(*args):
    try:
        result = subprocess.run(['exiftool', *map(str, args)], capture_output=True, timeout=120)
    except FileNotFoundError as exc:
        raise ValueError('找不到 ExifTool，请安装或使用内置 ExifTool 的 App') from exc
    if result.returncode:
        raise ValueError('ExifTool: ' + result.stderr.decode('utf-8', errors='replace').strip())
    return result.stdout


def metadata(path):
    return json.loads(exiftool('-j', '-n', '-G1', path))[0]


def write_live_photo(source, output, identifier):
    """Source is an already separated still. Output must be a new temp file."""
    identifier = str(uuid.UUID(identifier)).upper()
    note = (b'Apple iOS\0\0\1MM' + struct.pack('>H', 1)
            + struct.pack('>HHII', 17, 2, 37, 32) + b'\0' * 4
            + identifier.encode('ascii') + b'\0\0')
    with open(source, 'rb') as src, open(output, 'xb') as dst:
        shutil.copyfileobj(src, dst, 1024 * 1024)
    before = metadata(source)
    with tempfile.TemporaryDirectory(prefix='motionphoto-note-') as directory:
        note_path = Path(directory) / 'note.bin'
        note_path.write_bytes(note)
        exiftool('-overwrite_original', '-P', f'-MakerNotes<={note_path}', output)
    after = metadata(output)
    if after.get('Apple:ContentIdentifier') != identifier:
        raise ValueError('图片配对标识写入失败')
    # Only manufacturer-private MakerNotes are replaced; standard EXIF and XMP remain.
    for key, value in before.items():
        if key.startswith(('IFD0:', 'ExifIFD:', 'GPS:', 'XMP-')) and 'MakerNote' not in key:
            if after.get(key) != value:
                raise ValueError(f'图片元数据未完整保留：{key}')
