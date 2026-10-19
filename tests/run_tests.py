#!/usr/bin/env python3
"""One command for local/CI tests; missing tools are failures, not skips."""

import argparse
import importlib.util
from pathlib import Path
import shutil
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="运行动态照片转换回归测试")
    parser.add_argument("--app", type=Path, help="改为测试打包后的 App 可执行文件（支持 --cli）")
    args = parser.parse_args()
    missing = [name for name in ("exiftool", "ffmpeg", "ffprobe") if not shutil.which(name)]
    missing += [
        name for name in ("lxml", "exiftool", "PIL", "pillow_heif", "six")
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        print("缺少测试依赖：" + ", ".join(missing), file=sys.stderr)
        print("安装方法见 docs/TESTING.md；测试未运行。", file=sys.stderr)
        return 2
    if args.app and not args.app.is_file():
        parser.error(f"App 可执行文件不存在：{args.app}")
    if args.app and (args.app.parent.name != "MacOS" or args.app.parent.parent.name != "Contents" or args.app.parent.parent.parent.suffix != ".app"):
        parser.error("--app 应指向 .app/Contents/MacOS/ 下的可执行文件")

    sys.path.insert(0, str(ROOT))
    from tests import test_conversion
    test_conversion.APP_EXECUTABLE = args.app.resolve() if args.app else None
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
