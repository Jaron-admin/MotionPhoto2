"""Reverse CLI adapter, isolated from legacy defaults and destructive options."""
import json
from pathlib import Path
import signal
from .convert import convert_directory, convert_file


def run_reverse(args, parser):
    if bool(args.input_directory) == bool(args.input_image):
        parser.error('反向模式请选择一个输入文件夹或一张动态照片')
    rejected = ('input_video', 'output_file', 'delete_video', 'overwrite', 'keep_temp',
                'no_xmp', 'exif_match', 'copy_unmuxed', 'incremental_mode')
    if any(getattr(args, name) for name in rejected):
        parser.error('反向模式不使用配对、复制、覆盖、删除或单一输出文件选项；请用 --output-directory')
    if args.input_image and args.recursive:
        parser.error('单文件模式不使用 --recursive')

    def stop(signum, frame):
        raise KeyboardInterrupt

    old_handler = signal.signal(signal.SIGTERM, stop)
    try:
        if args.input_directory:
            results = convert_directory(args.input_directory, args.output_directory, args.recursive)
        else:
            source = Path(args.input_image).absolute()
            output = args.output_directory or source.parent.with_name(source.parent.name+'_实况照片')
            results = [convert_file(source, output)]
        errors = 0
        for result in results:
            print('[REVERSE] ' + json.dumps({'status': result.status, 'name': result.source.name,
                                           'message': result.message}, ensure_ascii=False), flush=True)
            errors += result.status == 'error'
        return 1 if errors else 0
    except KeyboardInterrupt:
        print('[INFO] 已停止，临时输出已清理。', flush=True)
        return 130
    except (ValueError, OSError) as exc:
        print('[ERROR] ' + str(exc), flush=True)
        return 1
    finally:
        signal.signal(signal.SIGTERM, old_handler)
