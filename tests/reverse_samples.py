"""Independent Google-format fixture builder (does not call forward Muxer)."""
from pathlib import Path
import shutil
import struct
from tests.generate_samples import run


def motion_photo(image, video, output, legacy=False, timestamp=200000, padding=0, offset_adjust=0):
    output = Path(output)
    shutil.copy2(image, output)
    heic = image.suffix.lower() in ('.heic', '.heif')
    length = video.stat().st_size + offset_adjust
    if legacy:
        content = f'''c:MicroVideo="1" c:MicroVideoVersion="1" c:MicroVideoOffset="{length}"
            c:MicroVideoPresentationTimestampUs="{timestamp}"'''
        directory = ''
    else:
        content = f'c:MotionPhoto="1" c:MotionPhotoVersion="1" c:MotionPhotoPresentationTimestampUs="{timestamp}"'
        directory = f'''<d:Directory><rdf:Seq>
          <rdf:li rdf:parseType="Resource"><d:Item i:Mime="{'image/heic' if heic else 'image/jpeg'}" i:Semantic="Primary" i:Length="0" i:Padding="{8 if heic else padding}"/></rdf:li>
          <rdf:li rdf:parseType="Resource"><d:Item i:Mime="video/mp4" i:Semantic="MotionPhoto" i:Length="{length}"/></rdf:li>
        </rdf:Seq></d:Directory>'''
    xmp = f'''<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <rdf:Description xmlns:c="http://ns.google.com/photos/1.0/camera/"
       xmlns:d="http://ns.google.com/photos/1.0/container/" xmlns:i="http://ns.google.com/photos/1.0/container/item/"
       {content}>{directory}</rdf:Description>
      <rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:description>Keep second description</dc:description></rdf:Description>
      </rdf:RDF></x:xmpmeta>'''
    xml = output.with_suffix('.xml')
    xml.write_text(xmp)
    run(['exiftool', '-overwrite_original', f'-XMP<={xml}', output])
    xml.unlink()
    with output.open('ab') as target:
        if heic:
            target.write(struct.pack('>I4s', video.stat().st_size+8, b'mpvd'))
        else:
            target.write(b'\0'*padding)
        target.write(video.read_bytes())
    return output
