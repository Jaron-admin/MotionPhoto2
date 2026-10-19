"""Validate Google Camera/Container XMP against actual image/video boundaries."""
from dataclasses import dataclass
import mmap
from pathlib import Path
from lxml import etree
from .iso_bmff import parse_atoms
from .photo import exiftool

CAMERA = 'http://ns.google.com/photos/1.0/camera/'
CONTAINER = 'http://ns.google.com/photos/1.0/container/'
ITEM = 'http://ns.google.com/photos/1.0/container/item/'
RDF = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
MOTION_FIELDS = {'MotionPhoto', 'MotionPhotoVersion', 'MotionPhotoPresentationTimestampUs',
                 'MicroVideo', 'MicroVideoVersion', 'MicroVideoOffset', 'MicroVideoPresentationTimestampUs'}


@dataclass(frozen=True)
class MotionPhoto:
    image_end: int
    video_start: int
    video_end: int
    timestamp_us: int | None
    suffix: str
    cleaned_xmp: bytes


def scalar(root, namespace, name):
    tag = '{' + namespace + '}' + name
    values = [el.attrib[tag] for el in root.iter() if tag in el.attrib]
    values += [el.text or '' for el in root.iter(tag)]
    if len(values) > 1:
        raise ValueError(f'XMP 字段重复：{name}')
    return values[0] if values else None


def integer(value, default=None):
    if value is None:
        return default
    if len(value) > 20 or not value.lstrip('-').isdigit():
        raise ValueError('XMP 整数字段无效')
    return int(value)


def jpeg_end(data):
    pos = 2
    while pos < len(data):
        if data[pos] != 255:
            raise ValueError('JPEG 标记无效')
        while pos < len(data) and data[pos] == 255:
            pos += 1
        if pos >= len(data):
            break
        marker = data[pos]
        pos += 1
        if marker == 0xD9:
            return pos
        if marker in (0, 0xD8) or 0xD0 <= marker <= 0xD7:
            raise ValueError('JPEG 标记顺序无效')
        if pos+2 > len(data):
            break
        length = int.from_bytes(data[pos:pos+2], 'big')
        if length < 2 or pos+length > len(data):
            raise ValueError('JPEG 段截断')
        if marker == 0xE2 and data[pos+2:pos+6] == b'MPF\0':
            raise ValueError('暂不支持多图层或增益图 JPEG')
        pos += length
        if marker == 0xDA:
            # Entropy-coded bytes escape FF as FF00; restart markers carry no length.
            while True:
                at = data.find(b'\xff', pos)
                if at < 0 or at+1 >= len(data):
                    raise ValueError('JPEG 扫描数据截断')
                next_at = at+1
                while next_at < len(data) and data[next_at] == 255:
                    next_at += 1
                if next_at >= len(data):
                    raise ValueError('JPEG 扫描数据截断')
                code = data[next_at]
                if code == 0 or 0xD0 <= code <= 0xD7:
                    pos = next_at+1
                    continue
                pos = at
                break
    raise ValueError('JPEG 缺少结束标记')


def clean_xmp(root):
    fields = {'{' + CAMERA + '}' + name for name in MOTION_FIELDS}
    fields.add('{' + CONTAINER + '}Directory')
    for element in list(root.iter()):
        for key in list(element.attrib):
            if key in fields:
                del element.attrib[key]
        if element.tag in fields and element.getparent() is not None:
            element.getparent().remove(element)
    return etree.tostring(root, encoding='UTF-8')


def detect(path):
    path = Path(path)
    xmp = exiftool('-b', '-XMP', path)
    if not xmp:
        return None
    if len(xmp) > 8 * 1024 * 1024 or b'<!DOCTYPE' in xmp or b'<!ENTITY' in xmp:
        raise ValueError('XMP 过大或包含不支持的实体声明')
    root = etree.fromstring(xmp, parser=etree.XMLParser(resolve_entities=False, no_network=True))
    current = scalar(root, CAMERA, 'MotionPhoto')
    legacy = scalar(root, CAMERA, 'MicroVideo')
    directories = list(root.iter('{' + CONTAINER + '}Directory'))
    if current is not None:
        if integer(current) != 1:
            return None
        if integer(scalar(root, CAMERA, 'MotionPhotoVersion')) != 1:
            raise ValueError('暂不支持此 Motion Photo 版本')
        if len(directories) != 1:
            raise ValueError('动态照片目录缺失或重复')
        directory = directories[0]
        seqs = list(directory)
        if len(seqs) != 1 or seqs[0].tag != '{'+RDF+'}Seq':
            raise ValueError('动态照片目录必须为有序列表')
        items = []
        for li in seqs[0]:
            candidates = list(li)
            if li.tag != '{'+RDF+'}li' or len(candidates) != 1 or candidates[0].tag != '{'+CONTAINER+'}Item':
                raise ValueError('动态照片目录条目结构无效')
            items.append(candidates[0])
        if len(items) != 2:
            raise ValueError('暂不支持含增益图或额外资源的动态照片')
        primary, video = items
        def field(item, name):
            return scalar(item, ITEM, name)
        if field(primary, 'Semantic') != 'Primary' or field(video, 'Semantic') != 'MotionPhoto':
            raise ValueError('动态照片目录顺序或语义无效')
        if integer(field(primary, 'Length'), 0) != 0 or integer(field(video, 'Padding'), 0) != 0:
            raise ValueError('动态照片长度或填充规则无效')
        mime = field(primary, 'Mime')
        if mime not in ('image/jpeg', 'image/heic') or field(video, 'Mime') not in ('video/mp4', 'video/quicktime'):
            raise ValueError('暂不支持该图片或视频类型')
        length = integer(field(video, 'Length'))
        padding = integer(field(primary, 'Padding'), 0)
        timestamp = integer(scalar(root, CAMERA, 'MotionPhotoPresentationTimestampUs'))
    else:
        if legacy != '1':
            return None
        if directories:
            raise ValueError('不能用旧偏移回退解析不完整的新格式目录')
        if integer(scalar(root, CAMERA, 'MicroVideoVersion')) != 1:
            raise ValueError('暂不支持此 MicroVideo 版本')
        length = integer(scalar(root, CAMERA, 'MicroVideoOffset'))
        timestamp = integer(scalar(root, CAMERA, 'MicroVideoPresentationTimestampUs'))
        padding, mime = 0, 'image/jpeg'
    if length is None or length <= 0 or padding < 0 or timestamp is not None and timestamp < -1:
        raise ValueError('动态照片长度或时间无效')
    for element in root.iter():
        for name in [element.tag, *element.attrib]:
            if isinstance(name, str) and any(word in name.lower() for word in ('hdrgainmap', 'hdr-gain-map', 'depthmap', 'gdepth')):
                raise ValueError('暂不支持 HDR、增益图或深度照片')
    with path.open('rb') as source:
        if path.stat().st_size < 8:
            raise ValueError('动态照片文件截断')
        with mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
            start = len(data) - length
            if start <= 0 or start+8 > len(data):
                raise ValueError('动态视频长度越界')
            if data[:2] == b'\xff\xd8':
                if mime != 'image/jpeg':
                    raise ValueError('图片结构与目录类型不一致')
                end = jpeg_end(data)
                if end + padding != start:
                    raise ValueError('图片结束位置与视频偏移不一致')
                suffix = '.JPG'
            else:
                if mime != 'image/heic':
                    raise ValueError('暂不支持该图片结构')
                top = parse_atoms(data)
                if not top or top[0].type != b'ftyp' or not any(brand in top[0].raw(data) for brand in (b'heic', b'heix')):
                    raise ValueError('暂不支持该 HEIF 编码')
                mpvd = [b for b in top if b.type == b'mpvd']
                if len(mpvd) != 1 or mpvd[0] is not top[-1] or mpvd[0].payload_start != start or mpvd[0].header_size != padding or data[mpvd[0].start:mpvd[0].start+4] == b'\0'*4:
                    raise ValueError('HEIC 的 mpvd 与 XMP 视频长度不一致')
                end = mpvd[0].start
                # Inspect only structured image properties, never scan compressed payload.
                for box in top:
                    if box.type == b'meta':
                        for child in parse_atoms(data, box.payload_start+4, box.end):
                            if child.type == b'iprp':
                                for ipco in parse_atoms(data, child.payload_start, child.end):
                                    if ipco.type == b'ipco':
                                        for prop in parse_atoms(data, ipco.payload_start, ipco.end):
                                            if prop.type == b'auxC':
                                                raise ValueError('暂不支持 HEIC 辅助图层')
                                            if prop.type == b'colr':
                                                value = data[prop.payload_start:prop.end]
                                                if value[:4] in (b'nclc', b'nclx') and len(value) >= 10 and int.from_bytes(value[6:8], 'big') in (16, 18):
                                                    raise ValueError('暂不支持 HDR HEIC')
                suffix = '.HEIC'
            if data[start+4:start+8] != b'ftyp':
                raise ValueError('偏移位置不是完整视频容器')
            total = len(data)
    return MotionPhoto(end, start, total, timestamp, suffix, clean_xmp(root))
