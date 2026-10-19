"""Independent decoders catch media/metadata loss in the reverse writers."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
from PIL import Image
from tests.generate_samples import generate_samples, run, CONTENT_ID, CAPTURE_TIME


class ReverseMediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='reverse-media-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.samples = generate_samples(cls.root / 'samples')
        cls.movie = cls.root / 'source.mp4'
        run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=96x64:rate=30',
             '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1',
             '-c:v', 'libx264', '-c:a', 'aac', '-threads', '1', cls.movie])

    def test_photo_preserves_pixels_and_metadata_in_both_formats(self):
        from reverse.photo import write_live_photo
        for suffix in ('JPG', 'HEIC'):
            with self.subTest(suffix=suffix):
                source = self.samples / ('PHOTO.' + suffix)
                output = self.root / ('output.' + suffix)
                write_live_photo(source, output, CONTENT_ID)
                meta = json.loads(run(['exiftool', '-j', '-n', '-ee', output]))[0]
                self.assertEqual(meta['ContentIdentifier'], CONTENT_ID)
                self.assertEqual(meta['Make'], 'Apple')
                self.assertEqual(meta['DateTimeOriginal'], CAPTURE_TIME)
                self.assertEqual(meta['GPSLatitude'], 1)
                self.assertEqual(Image.open(source).tobytes(), Image.open(output).tobytes())
                self.assertEqual(meta['Description'], 'Synthetic regression fixture')

    def test_mov_preserves_encoded_packets_and_selects_presentation_frame(self):
        from reverse.quicktime import write_live_mov
        output = self.root / 'output.mov'
        selected = write_live_mov(self.movie, output, CONTENT_ID, 510000)
        self.assertAlmostEqual(float(selected), 0.5, places=6)
        meta = json.loads(run(['exiftool', '-j', '-n', '-ee', output]))[0]
        self.assertEqual(meta['ContentIdentifier'], CONTENT_ID)
        self.assertIn('StillImageTime', meta)
        self.assertEqual(output.read_bytes()[8:12], b'qt  ')
        for stream in ('v:0', 'a:0'):
            def packets(path):
                return json.loads(run(['ffprobe', '-v', 'error', '-select_streams', stream,
                    '-show_packets', '-show_data_hash', 'sha256', '-of', 'json', path]))['packets']
            before, after = packets(self.movie), packets(output)
            self.assertEqual([(p['pts_time'], p['dts_time'], p['data_hash']) for p in before],
                             [(p['pts_time'], p['dts_time'], p['data_hash']) for p in after])
        info = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', output]))
        timed = next(s for s in info['streams'] if s.get('codec_tag_string') == 'mebx')
        self.assertAlmostEqual(float(timed['start_time']), 0.5, places=4)
        run(['ffmpeg', '-v', 'error', '-i', output, '-f', 'null', '-'])

    def test_rejects_out_of_range_time_and_truncated_movie(self):
        from reverse.quicktime import write_live_mov
        for timestamp in (-2, 1000000, 5000000):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                write_live_mov(self.movie, self.root / 'invalid.mov', CONTENT_ID, timestamp)
        truncated = self.root / 'truncated.mp4'
        truncated.write_bytes(self.movie.read_bytes()[:-1])
        with self.assertRaises(ValueError):
            write_live_mov(truncated, self.root / 'invalid.mov', CONTENT_ID, None)
        self.assertFalse((self.root / 'invalid.mov').exists())

    def test_fragmented_movie_is_rejected_without_output(self):
        from reverse.quicktime import write_live_mov
        fragmented = self.root / 'fragmented.mp4'
        run(['ffmpeg', '-v', 'error', '-i', self.movie, '-c', 'copy', '-movflags',
             'frag_keyframe+empty_moov', fragmented])
        with self.assertRaises(ValueError):
            write_live_mov(fragmented, self.root / 'fragmented.mov', CONTENT_ID, None)
        self.assertFalse((self.root / 'fragmented.mov').exists())

    def test_corrupt_chunk_offset_and_external_reference_are_rejected(self):
        from reverse.quicktime import write_live_mov
        raw = self.movie.read_bytes()
        for name, marker, delta, replacement in (
            ('offset', b'stco', 12, b'\xff'*4),
            ('external', b'url ', 4, b'\0'*4),
        ):
            altered = bytearray(raw)
            at = altered.index(marker) + delta
            altered[at:at+4] = replacement
            source = self.root/(name+'.mp4')
            source.write_bytes(altered)
            output = self.root/(name+'.mov')
            with self.subTest(name=name), self.assertRaises(ValueError):
                write_live_mov(source, output, CONTENT_ID, None)
            self.assertFalse(output.exists())

    def test_hevc_rotation_and_extra_media_box_survive_remux(self):
        from reverse.quicktime import write_live_mov
        source = self.root/'hevc.mp4'
        run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=96x64:rate=10', '-t', '0.5',
             '-c:v', 'libx265', '-x265-params', 'log-level=error:pools=1', '-tag:v', 'hvc1', source])
        run(['exiftool', '-overwrite_original', '-Rotation=90', source])
        # A second mdat must not cause the first one's bytes to be dropped.
        with source.open('ab') as output:
            output.write(struct.pack('>I4s', 12, b'mdat') + b'test')
        output = self.root/'hevc.mov'
        write_live_mov(source, output, CONTENT_ID, -1)
        info = json.loads(run(['exiftool', '-j', '-n', output]))[0]
        self.assertEqual(info['Rotation'], 90)
        run(['ffmpeg', '-v', 'error', '-i', output, '-f', 'null', '-'])

    def test_mp3_in_mp4a_is_not_misidentified_as_aac(self):
        from reverse.quicktime import write_live_mov
        source = self.root/'mp3-in-mp4.mp4'
        run(['ffmpeg', '-v', 'error', '-i', self.movie, '-c:v', 'copy', '-c:a', 'libmp3lame', source])
        info = json.loads(run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_streams', '-of', 'json', source]))
        self.assertEqual(info['streams'][0]['codec_tag_string'], 'mp4a')
        self.assertEqual(info['streams'][0]['codec_name'], 'mp3')
        with self.assertRaisesRegex(ValueError, 'AAC'):
            write_live_mov(source, self.root/'mp3-in-mp4.mov', CONTENT_ID, None)

    def test_box_flood_is_rejected_before_allocating_an_unbounded_index(self):
        from reverse.iso_bmff import parse_atoms
        # Just 1 MiB of tiny boxes previously allocated ~18 MiB Python heap.
        payload = struct.pack('>I4s', 8, b'free') * 131072
        with self.assertRaises(ValueError):
            parse_atoms(payload)
