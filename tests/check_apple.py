#!/usr/bin/env python3
"""Synthetic Apple acceptance probe, separate from portable tests. No library writes."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.generate_samples import generate_samples, run
from tests.reverse_samples import motion_photo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='motionphoto-apple-check-') as temporary:
        root = Path(temporary)
        samples = generate_samples(root/'samples')
        command = [sys.executable, str(ROOT/'mac_gui.py'), '--cli']
        if args.app:
            original = args.app.resolve()
            bundle = original.parent.parent.parent
            copied = root/bundle.name
            shutil.copytree(bundle, copied, symlinks=True)
            command = [str(copied/original.relative_to(bundle)), '--cli']
        inputs = root/'inputs'
        inputs.mkdir()
        for suffix in ('JPG', 'HEIC'):
            source = inputs/f'Pixel-{suffix}.{suffix}'
            motion_photo(samples/f'PHOTO.{suffix}', samples/'PHOTO.MOV', source)
            run(['exiftool', '-overwrite_original', '-Make=Google', '-Model=Synthetic Pixel', source])
            output = root/('output-'+suffix)
            run(command+['--direction', 'motion-to-live', '--input-image', source, '--output-directory', output])
            result = subprocess.run(['xcrun', 'swift', '-module-cache-path', str(root/'swift-cache'),
                str(ROOT/'tests/verify_live_photo.swift'), str(output/source.name), str(output/(source.stem+'.MOV'))],
                text=True, capture_output=True, timeout=90)
            print(suffix, result.stdout.strip(), flush=True)
            if result.returncode:
                print(result.stderr, file=sys.stderr)
                return result.returncode
    return 0


if __name__ == '__main__':
    sys.exit(main())
