"""Small regressions for existing keyframe and video-signature behavior."""

import unittest

from utils import extract_track_duration, extract_track_number, verify_video_in_image


class MetadataTests(unittest.TestCase):
    def test_keyframe_uses_its_own_track_and_microseconds(self):
        metadata = """
            <Track1:TrackDuration>3</Track1:TrackDuration>
            <Track3:TrackDuration>1.234567</Track3:TrackDuration>
            <Track3:StillImageTime>-1</Track3:StillImageTime>
        """
        track = extract_track_number(metadata)
        self.assertEqual(track, "3")
        self.assertEqual(extract_track_duration(track, metadata), "1234567")

    def test_video_signature_accepts_mov_and_mp4(self):
        for data in (b"\0\0\0\x14ftypqt  ", b"\0\0\0\x20ftypisom", b"\0\0\0\x08wide"):
            with self.subTest(data=data):
                self.assertTrue(verify_video_in_image(data))

    def test_image_audio_and_empty_payloads_are_not_videos(self):
        for data in (b"", b"not a video", b"\0\0\0\x20ftypheic", b"\0\0\0\x20ftypavif", b"\0\0\0\x20ftypM4A "):
            with self.subTest(data=data):
                self.assertFalse(verify_video_in_image(data))
