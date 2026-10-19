"""Read-only source conversion with no-clobber pair publication."""
from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
import uuid
from .detect import detect
from .photo import exiftool, write_live_photo
from .quicktime import write_live_mov


@dataclass(frozen=True)
class Result:
    source: Path
    status: str
    message: str
    paths: tuple = ()


def validate_output(source_directory, output):
    source_directory, output = Path(source_directory).resolve(), Path(output).resolve()
    if output == source_directory or source_directory in output.parents:
        raise ValueError('输出文件夹不能是输入文件夹或其子文件夹')
    return output


def copy_range(source, output, start, end):
    source.seek(start)
    with output.open('xb') as target:
        remaining = end-start
        while remaining:
            block = source.read(min(remaining, 1024*1024))
            if not block:
                raise ValueError('转换期间源文件被截断')
            target.write(block)
            remaining -= len(block)


def publish_pair(staged, targets):
    published = []
    try:
        for source, target in zip(staged, targets):
            published.append((source, target))
            os.link(source, target)  # Atomic; fails if even a dangling link exists.
    except BaseException:
        for source, target in reversed(published):
            # Never remove a file another process replaced while publication was in flight.
            try:
                if os.path.samestat(source.stat(), target.lstat()):
                    target.unlink()
            except FileNotFoundError:
                pass
        raise


def convert_file(source, output):
    source = Path(source).absolute()
    try:
        if source.is_symlink() or not source.is_file():
            raise ValueError('输入必须是普通文件，暂不处理符号链接')
        output = validate_output(source.parent, output)
        before = source.stat()
        motion = detect(source)
        if motion is None:
            return Result(source, 'plain', '普通照片或没有有效动态照片标志，已跳过')
        targets = (output / (source.stem + motion.suffix), output / (source.stem + '.MOV'))
        if any(os.path.lexists(path) for path in targets):
            return Result(source, 'skipped', '存在同名文件（可能是不完整配对），整对跳过')
        output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.motionphoto-', dir=output) as temporary:
            temporary = Path(temporary)
            still = temporary / ('still' + motion.suffix)
            video = temporary / 'video.mp4'
            with source.open('rb') as src:
                copy_range(src, still, 0, motion.image_end)
                copy_range(src, video, motion.video_start, motion.video_end)
            # Clean only obsolete Motion Photo properties; keep all other RDF descriptions.
            xml = temporary / 'clean.xmp'
            xml.write_bytes(motion.cleaned_xmp)
            exiftool('-overwrite_original', '-P', f'-XMP<={xml}', still)
            maker_note = exiftool('-b', '-MakerNotes', still)
            identifier = str(uuid.uuid4()).upper()
            ready = temporary / 'ready'
            ready.mkdir()
            staged = (ready / targets[0].name, ready / targets[1].name)
            write_live_photo(still, staged[0], identifier)
            selected = write_live_mov(video, staged[1], identifier, motion.timestamp_us)
            after = source.stat()
            if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                raise ValueError('源文件在转换期间发生变化，已取消输出')
            for path in staged:
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
            publish_pair(staged, targets)
        warning = '；厂商私有 MakerNote 已替换，原始信息保留在源文件' if maker_note and not maker_note.startswith(b'Apple iOS') else ''
        rule = '采用中间帧' if motion.timestamp_us in (None, -1) else '采用指定时间之前的显示帧'
        return Result(source, 'converted', f'已生成实况照片；{rule} {float(selected):.3f} 秒{warning}', targets)
    except FileExistsError:
        return Result(source, 'skipped', '输出期间出现同名文件，已取消整对输出')
    except Exception as exc:
        # KeyboardInterrupt/SystemExit deliberately propagate so cancellation cannot be success.
        message = str(exc)
        status = 'unsupported' if message.startswith(('暂不支持', '不支持')) else 'error'
        return Result(source, status, message)


def convert_directory(source, output=None, recursive=False):
    source = Path(source).resolve()
    if not source.is_dir():
        raise ValueError('输入文件夹不存在')
    output = validate_output(source, output or source.with_name(source.name+'_实况照片'))
    files = sorted(p for p in (source.rglob('*') if recursive else source.iterdir())
                   if p.is_file() and p.suffix.lower() in {'.jpg', '.jpeg', '.heic', '.heif'})
    for path in files:
        destination = output / path.relative_to(source).parent
        resolved = destination.resolve()
        if (resolved != output and output not in resolved.parents) or resolved == source or source in resolved.parents:
            yield Result(path, 'error', '输出子目录被符号链接重定向，已跳过')
            continue
        yield convert_file(path, destination)
