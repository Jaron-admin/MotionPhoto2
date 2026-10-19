"""Bounded, lossless MOV remux. Media offsets stay fixed; old moov becomes free.

Only progressive, self-contained H.264/HEVC + optional AAC is accepted. The
sample tables are checked before any output is created. No ffmpeg is required.
"""
from fractions import Fraction
import mmap
from pathlib import Path
import struct
import uuid

from .iso_bmff import atom, parse_atoms, child_atoms
from .metadata import _timed_metadata_track, TIMED_SAMPLE
from .photo import exiftool

MAX_SAMPLES = 1_000_000


def one(data, parent, kind, optional=False):
    matches = [b for b in child_atoms(data, parent) if b.type == kind]
    if not matches and optional:
        return None
    if len(matches) != 1:
        raise ValueError(f'容器缺少或重复 {kind.decode("ascii")} 段')
    return matches[0]


def payload(data, box, minimum=0):
    value = data[box.payload_start:box.end]
    if len(value) < minimum:
        raise ValueError('容器字段截断')
    return value


def clock(data, box):
    p = payload(data, box, 20)
    version = p[0]
    if version not in (0, 1):
        raise ValueError('不支持的时间头版本')
    offset = 20 if version else 12
    if len(p) < offset + (12 if version else 8):
        raise ValueError('时间头截断')
    scale = int.from_bytes(p[offset:offset+4], 'big')
    duration = int.from_bytes(p[offset+4:offset+(12 if version else 8)], 'big')
    if not scale or not duration:
        raise ValueError('无效的视频时间基准或长度')
    return scale, duration


def entries(data, box, width):
    p = payload(data, box, 8)
    count = int.from_bytes(p[4:8], 'big')
    if count > MAX_SAMPLES or len(p) != 8 + count * width:
        raise ValueError('采样表长度无效或超过安全上限')
    return [p[i:i+width] for i in range(8, len(p), width)]


def track_info(data, track, mdats, movie_scale):
    tkhd = one(data, track, b'tkhd')
    p = payload(data, tkhd, 24)
    if p[0] not in (0, 1):
        raise ValueError('不支持的轨道头版本')
    tid_at = 20 if p[0] else 12
    track_id = int.from_bytes(p[tid_at:tid_at+4], 'big')
    mdia = one(data, track, b'mdia')
    handler = payload(data, one(data, mdia, b'hdlr'), 12)[8:12]
    if handler not in (b'vide', b'soun'):
        raise ValueError('暂不支持包含辅助或额外元数据轨道的视频')
    scale, duration = clock(data, one(data, mdia, b'mdhd'))
    minf = one(data, mdia, b'minf')
    dinf = one(data, minf, b'dinf')
    dref = payload(data, one(data, dinf, b'dref'), 8)
    refs = parse_atoms(dref, 8)
    if len(refs) != 1 or int.from_bytes(dref[4:8], 'big') != 1:
        raise ValueError('暂不支持多媒体引用')
    ref = refs[0]
    if ref.type not in (b'url ', b'alis') or payload(dref, ref, 4)[:4] != b'\0\0\0\1':
        raise ValueError('不支持外部媒体引用')
    stbl = one(data, minf, b'stbl')
    supported = {b'stsd', b'stts', b'ctts', b'stsc', b'stsz', b'stco', b'co64', b'stss', b'sdtp', b'sgpd', b'sbgp'}
    if any(b.type not in supported for b in child_atoms(data, stbl)):
        raise ValueError('暂不支持该采样表或加密视频')
    sd = payload(data, one(data, stbl, b'stsd'), 8)
    descriptions = parse_atoms(sd, 8)
    if len(descriptions) != 1 or int.from_bytes(sd[4:8], 'big') != 1:
        raise ValueError('暂不支持多个采样描述')
    desc = descriptions[0]
    codecs = (b'avc1', b'avc3', b'hvc1', b'hev1') if handler == b'vide' else (b'mp4a',)
    if desc.type not in codecs:
        raise ValueError('暂不支持该视频/音频编码（需要 H.264/HEVC 和 AAC）')
    description = payload(sd, desc, 8)
    if description[6:8] != b'\0\1':
        raise ValueError('无效的采样媒体引用')
    if handler == b'vide':
        if len(description) < 78:
            raise ValueError('视频采样描述截断')
        for extra in parse_atoms(description, 78):
            if extra.type == b'colr':
                color = payload(description, extra, 4)
                if color[:4] in (b'nclc', b'nclx') and len(color) >= 10 and int.from_bytes(color[6:8], 'big') in (16, 18):
                    raise ValueError('暂不支持 HDR 视频')
            if extra.type == b'sinf':
                raise ValueError('不支持加密视频')
    size_data = payload(data, one(data, stbl, b'stsz'), 12)
    fixed, count = struct.unpack('>II', size_data[4:12])
    if not count or count > MAX_SAMPLES or len(size_data) != 12 + (0 if fixed else count * 4):
        raise ValueError('采样大小表无效')
    sizes = [fixed] * count if fixed else list(struct.unpack(f'>{count}I', size_data[12:]))
    if any(size == 0 for size in sizes):
        raise ValueError('空媒体采样')
    co = one(data, stbl, b'stco', True)
    co64 = one(data, stbl, b'co64', True)
    if bool(co) == bool(co64):
        raise ValueError('无效的媒体偏移表')
    offsets = [int.from_bytes(v, 'big') for v in entries(data, co or co64, 4 if co else 8)]
    chunks = [struct.unpack('>III', v) for v in entries(data, one(data, stbl, b'stsc'), 12)]
    if not chunks or chunks[0][0] != 1 or any(n == 0 or d != 1 for _, n, d in chunks):
        raise ValueError('媒体分块表无效')
    if any(a[0] >= b[0] for a, b in zip(chunks, chunks[1:])) or chunks[-1][0] > len(offsets):
        raise ValueError('媒体分块顺序无效')
    consumed = 0
    index = 0
    for number, offset in enumerate(offsets, 1):
        if index + 1 < len(chunks) and number >= chunks[index+1][0]:
            index += 1
        n = chunks[index][1]
        if consumed + n > count:
            raise ValueError('媒体采样数不一致')
        end = offset + sum(sizes[consumed:consumed+n])
        if not any(m.payload_start <= offset < end <= m.end for m in mdats):
            raise ValueError('媒体采样指向视频数据之外')
        consumed += n
    if consumed != count:
        raise ValueError('媒体采样数不一致')
    deltas = []
    for value in entries(data, one(data, stbl, b'stts'), 8):
        n, delta = struct.unpack('>II', value)
        if not n or not delta or len(deltas) + n > count:
            raise ValueError('解码时间表无效')
        deltas.extend([delta] * n)
    if len(deltas) != count or sum(deltas) != duration:
        raise ValueError('解码时间与采样长度不一致')
    ctts = one(data, stbl, b'ctts', True)
    composition = [0] * count
    if ctts:
        version = payload(data, ctts, 8)[0]
        if version not in (0, 1):
            raise ValueError('不支持的显示时间表版本')
        composition = []
        for value in entries(data, ctts, 8):
            n = int.from_bytes(value[:4], 'big')
            offset = int.from_bytes(value[4:], 'big', signed=version == 1)
            if not n or len(composition) + n > count:
                raise ValueError('显示时间表无效')
            composition.extend([offset] * n)
        if len(composition) != count:
            raise ValueError('显示时间与采样数不一致')
    empty = Fraction(0)
    media_start = 0
    visible = Fraction(duration, scale)
    edts = one(data, track, b'edts', True)
    if edts:
        elst = one(data, edts, b'elst')
        version = payload(data, elst, 8)[0]
        if version not in (0, 1):
            raise ValueError('不支持的编辑列表版本')
        edits = entries(data, elst, 20 if version else 12)
        if not 1 <= len(edits) <= 2:
            raise ValueError('暂不支持复杂编辑列表')
        for i, value in enumerate(edits):
            segment, start, rate, frac = struct.unpack('>Qqhh' if version else '>Iihh', value)
            if rate != 1 or frac != 0 or not segment:
                raise ValueError('暂不支持变速或空编辑片段')
            if start == -1 and i == 0 and len(edits) == 2:
                empty = Fraction(segment, movie_scale)
            elif start >= 0 and i == len(edits)-1:
                media_start, visible = start, Fraction(segment, movie_scale)
            else:
                raise ValueError('暂不支持该编辑列表')
    frames = []
    dts = 0
    for delta, offset in zip(deltas, composition):
        pts = Fraction(dts + offset - media_start, scale)
        if 0 <= pts < visible:
            frames.append(empty + pts)
        dts += delta
    return track_id, handler, sorted(frames), empty + visible


def write_live_mov(source, output, identifier, timestamp_us=None):
    identifier = str(uuid.UUID(identifier)).upper()
    if timestamp_us is not None and (not isinstance(timestamp_us, int) or timestamp_us < -1):
        raise ValueError('封面时间无效')
    with open(source, 'rb') as src:
        if Path(source).stat().st_size < 8:
            raise ValueError('视频为空或截断')
        with mmap.mmap(src.fileno(), 0, access=mmap.ACCESS_READ) as data:
            top = parse_atoms(data)
            if any(b.type not in {b'ftyp', b'moov', b'mdat', b'free', b'skip', b'wide'} for b in top):
                raise ValueError('暂不支持碎片化或额外容器段')
            movies = [b for b in top if b.type == b'moov']
            types = [b for b in top if b.type == b'ftyp']
            mdats = [b for b in top if b.type == b'mdat']
            if len(movies) != 1 or len(types) != 1 or not mdats:
                raise ValueError('视频必须包含一个 ftyp、一个 moov 以及媒体数据')
            moov, ftyp = movies[0], types[0]
            if moov.size > 32 * 1024 * 1024 or ftyp.size > 4096:
                raise ValueError('视频索引超过安全上限')
            if ftyp.size < ftyp.header_size + 8 or (ftyp.size-ftyp.header_size) % 4:
                raise ValueError('视频类型头无效')
            mvhd = one(data, moov, b'mvhd')
            scale, duration = clock(data, mvhd)
            tracks = [b for b in child_atoms(data, moov) if b.type == b'trak']
            if any(b.type in {b'mvex', b'cmov'} for b in child_atoms(data, moov)):
                raise ValueError('不支持碎片化或压缩索引')
            infos = [track_info(data, track, mdats, scale) for track in tracks]
            videos = [i for i in infos if i[1] == b'vide']
            if len(videos) != 1 or len(infos) > 2:
                raise ValueError('需要一个视频轨道，最多一个音频轨道')
            ids = [i[0] for i in infos]
            if len(set(ids)) != len(ids) or not all(0 < i < 0xFFFFFFFE for i in ids):
                raise ValueError('轨道标识无效')
            video_id, _, frames, visible = videos[0]
            if not frames:
                raise ValueError('视频没有可显示帧')
            target = visible / 2 if timestamp_us in (None, -1) else Fraction(timestamp_us, 1_000_000)
            if target < frames[0] or target >= visible:
                raise ValueError('封面时间超出视频展示范围')
            selected = max(frame for frame in frames if frame <= target)
            cover = round(selected * scale)
            if cover >= duration or cover + 1 > 0xFFFFFFFF:
                raise ValueError('封面时间超出影片时间范围')
            movie = bytearray(moov.raw(data))
            local_mvhd = next(b for b in child_atoms(movie, parse_atoms(movie)[0]) if b.type == b'mvhd')
            movie[local_mvhd.end-4:local_mvhd.end] = struct.pack('>I', max(ids)+2)
            additions = _timed_metadata_track(max(ids)+1, video_id, scale, cover, len(data)+8)
            # Preserve every original byte offset, including multiple mdat boxes and co64.
            with open(output, 'xb') as dst:
                for box in top:
                    if box is moov:
                        dst.write(struct.pack('>I4s', box.size, b'free'))
                        remaining = box.size - 8
                        while remaining:
                            n = min(remaining, 1024 * 1024)
                            dst.write(b'\0' * n)
                            remaining -= n
                    elif box is ftyp:
                        dst.write(atom(b'ftyp', b'qt  ' + b'\0' * 4 + b'qt  ' * ((box.size-16)//4)))
                    else:
                        # Explicit size prevents a size=0 mdat swallowing the appended moov.
                        if data[box.start:box.start+4] == b'\0'*4:
                            if box.size > 0xFFFFFFFF:
                                raise ValueError('暂不支持超过 4GiB 的无长度媒体段')
                            dst.write(struct.pack('>I', box.size))
                            start = box.start+4
                        else:
                            start = box.start
                        for at in range(start, box.end, 1024 * 1024):
                            dst.write(data[at:min(at+1024*1024, box.end)])
                dst.write(atom(b'mdat', TIMED_SAMPLE))
                dst.write(atom(b'moov', movie[moov.header_size:] + additions))
    # ExifTool merges this into existing QuickTime keys, retaining source metadata.
    exiftool('-overwrite_original', '-P', f'-Keys:ContentIdentifier={identifier}', output)
    return selected
