# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
# Adapted from yangzhen-23/video-to-live-photo, commit 83b55e6.
# Modified for MotionPhoto2: retained only metadata atom construction.
import struct
from .iso_bmff import atom

STILL_TIME_KEY = b"com.apple.quicktime.still-image-time"
TIMED_SAMPLE = b"\x00\x00\x00\x09\x00\x00\x00\x01\xff"

def _fullbox(version: int = 0, flags: int = 0) -> bytes:
    return bytes((version,)) + flags.to_bytes(3, "big")


def _pascal(text: bytes) -> bytes:
    if len(text) > 255:
        raise ValueError("Pascal 字符串过长")
    return bytes((len(text),)) + text


def _timed_metadata_track(
    track_id: int,
    video_track_id: int,
    timescale: int,
    cover_ticks: int,
    sample_offset: int,
) -> bytes:
    track_duration = cover_ticks + 1
    matrix = struct.pack(
        ">9I",
        0x00010000,
        0,
        0,
        0,
        0x00010000,
        0,
        0,
        0,
        0x40000000,
    )
    tkhd = atom(
        b"tkhd",
        _fullbox(flags=0x0F)
        + struct.pack(">IIIII", 0, 0, track_id, 0, track_duration)
        + b"\x00" * 8
        + struct.pack(">hhhh", 0, 0, 0, 0)
        + matrix
        + struct.pack(">II", 0, 0),
    )

    edits: list[bytes] = []
    if cover_ticks:
        edits.append(struct.pack(">IiHH", cover_ticks, -1, 1, 0))
    edits.append(struct.pack(">IiHH", 1, 0, 1, 0))
    elst = atom(b"elst", _fullbox() + struct.pack(">I", len(edits)) + b"".join(edits))
    edts = atom(b"edts", elst)
    tref = atom(b"tref", atom(b"cdsc", struct.pack(">I", video_track_id)))

    mdhd = atom(
        b"mdhd",
        _fullbox()
        + struct.pack(">IIII", 0, 0, timescale, 1)
        + struct.pack(">HH", 0x55C4, 0),
    )
    metadata_name = b"Core Media Metadata"
    hdlr = atom(
        b"hdlr",
        _fullbox()
        + b"mhlrmetaappl"
        + struct.pack(">II", 1, 0)
        + _pascal(metadata_name),
    )

    gmin = atom(
        b"gmin",
        _fullbox() + struct.pack(">H3HHH", 0x0040, 0x8000, 0x8000, 0x8000, 0, 0),
    )
    gmhd = atom(b"gmhd", gmin)
    data_name = b"Core Media Data Handler"
    data_hdlr = atom(
        b"hdlr",
        _fullbox()
        + b"dhlralisappl"
        + struct.pack(">II", 0, 0)
        + _pascal(data_name),
    )
    alias = atom(b"alis", _fullbox(flags=1))
    dref = atom(b"dref", _fullbox() + struct.pack(">I", 1) + alias)
    dinf = atom(b"dinf", dref)

    keyd = atom(b"keyd", b"mdta" + STILL_TIME_KEY)
    dtyp = atom(b"dtyp", _fullbox() + struct.pack(">I", 0x41))
    key_record = struct.pack(">II", 8 + len(keyd) + len(dtyp), 1) + keyd + dtyp
    keys = atom(b"keys", key_record)
    mebx = atom(b"mebx", b"\x00" * 6 + struct.pack(">H", 1) + keys)
    stsd = atom(b"stsd", _fullbox() + struct.pack(">I", 1) + mebx)
    stts = atom(b"stts", _fullbox() + struct.pack(">III", 1, 1, 1))
    stsc = atom(b"stsc", _fullbox() + struct.pack(">IIII", 1, 1, 1, 1))
    stsz = atom(b"stsz", _fullbox() + struct.pack(">II", 0, 1) + struct.pack(">I", len(TIMED_SAMPLE)))
    if sample_offset <= 0xFFFFFFFF:
        chunk_offsets = atom(b"stco", _fullbox() + struct.pack(">II", 1, sample_offset))
    else:
        chunk_offsets = atom(b"co64", _fullbox() + struct.pack(">IQ", 1, sample_offset))
    stbl = atom(b"stbl", stsd + stts + stsc + stsz + chunk_offsets)
    minf = atom(b"minf", gmhd + data_hdlr + dinf + stbl)
    mdia = atom(b"mdia", mdhd + hdlr + minf)
    return atom(b"trak", tkhd + edts + tref + mdia)



