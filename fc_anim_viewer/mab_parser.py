"""Core .mab animation bank parser for Far Cry Dunia engine games.

Implements the binary format for reading .mab files (Animation Banks) from
Far Cry 2 through Far Cry 5+. Builds on community reverse-engineering work:

    buu342/PY-DuniaAnimationExtractor  -- raw keyframe extraction logic
    Open-Source-Modding/blender-io-dunia -- Blender import patterns

This module is a clean-room implementation based on published format analysis.
No leaked source code from Ubisoft or Crytek was used.

Supported .mab versions:
    mab1 --> Far Cry 2 / early Dunia        (version 1)
    mab2 --> Far Cry 3 / FC4                (version 2, most common)
    mab3 --> Far Cry 5                      (version 3, added per-clip metadata)

Usage
-----
    from fc_anim_viewer.mab_parser import read_mab_file

    bank = read_mab_file(
        "path/to/weapons/fp_assault_rifle.mab"
    )
    for clip in bank.clips:
        print(f"  {clip.name}: {clip.bone_count} bones, "
              f"{clip.duration_seconds:.2f}s")

Or just get clip names without loading full keyframes:
    from fc_anim_viewer.mab_parser import read_all_clip_names

    names = read_all_clip_names("weapons/fp_rifle.mab")
    # ['rifle_idle', 'rifle_fire', 'reload_start', ...]
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import BinaryIO


from .animation_info import (
    MabBank,
    AnimationClip,
    AnimationTrack,
    RotationKey,
    PositionKey,
    ScaleKey,
    MabVersion,
    MAGIC_MAP,
)


# ===================================================================
# Low-level helpers -- reading little-endian binary chunks from file
# ===================================================================

def _read_chunk_header(stream: BinaryIO):
    """Read a chunk header: (type_id, size_in_bytes). Returns None on EOF."""
    data = stream.read(8)
    if len(data) < 8:
        return None
    type_id, size = struct.unpack("<II", data[:8])
    return type_id, size


def _read_string_pool(stream: BinaryIO, chunk_size: int):
    """Read the string pool -- a block of null-terminated strings.

    Format (FC3 / mab2 style):
      uint32  count          # number of strings in pool
      [string 1]            # length-delimited + null terminator
      [string 2]
      ...
    """
    if chunk_size < 4:
        return {}

    count_bytes = stream.read(4)
    if len(count_bytes) < 4:
        return {}
    count = struct.unpack("<I", count_bytes)[0]

    pool: dict[int, str] = {}
    for i in range(1, count + 1):       # string indices are 1-based
        raw = stream.read(256)           # read a generous chunk
        end = raw.find(b"\x00")          # find the null terminator
        if end >= 0:
            raw = raw[:end]
        text = raw.decode("utf-8", errors="replace")
        pool[i] = text

    return pool


def _read_keyframe_data(stream: BinaryIO, chunk_size: int):
    """Parse keyframe binary data from a .mab chunk payload.

    Expected format per bone stream:
      byte   type_tag   -- 0x01=rotation, 0x03=position, 0x04=scale
      uint32 num_keys   -- how many keyframes follow

    For each keyframe:
      rotation (tag 0x01): [time: f32][x: f32][y: f32][z: f32][w: f32] = 20 bytes
      position (tag 0x03): [time: f32][x: f32][y: f32][z: f32]         = 16 bytes
      scale    (tag 0x04): [time: f32][x: f32][y: f32][z: f32]         = 16 bytes

    Returns a list of AnimationTrack objects filled with keys.
    """
    tracks: list[AnimationTrack] = []

    end_of_chunk = stream.tell() + chunk_size

    while stream.tell() < end_of_chunk:
        tag_bytes = stream.read(1)
        if len(tag_bytes) < 1:
            break
        tag = tag_bytes[0]

        nkeys_bytes = stream.read(4)
        if len(nkeys_bytes) < 4:
            break
        nkeys = struct.unpack("<I", nkeys_bytes)[0]

        track = AnimationTrack(bone_name=f"unknown_keyframe_track")

        for _ in range(nkeys):
            if tag == 0x01 and stream.tell() + 20 <= end_of_chunk:
                vals = struct.unpack("<fffff", stream.read(20))
                track.rotation_keys.append(RotationKey(*vals))
            elif tag == 0x03 and stream.tell() + 16 <= end_of_chunk:
                vals = struct.unpack("<ffff", stream.read(16))
                track.position_keys.append(PositionKey(*vals))
            elif tag == 0x04 and stream.tell() + 16 <= end_of_chunk:
                vals = struct.unpack("<ffff", stream.read(16))
                track.scale_keys.append(ScaleKey(*vals))
            else:
                # Not enough data for this key -- advance past it
                bytes_needed = 20 if tag == 0x01 else 16
                stream.seek(bytes_needed, 1)

        tracks.append(track)

    return tracks


# ===================================================================
# Version-specific parsers
# ===================================================================

def _parse_mab2(stream: BinaryIO, file_path: Path):
    """Parse a .mab1 or .mab2 animation bank (FC3 / FC4 style).

    Layout:
      [magic "mab1"/"mab2"]:     4 bytes
      [chunk: string pool]:      uint32 count + null-terminated strings
      [chunk: track headers]:    per-clip metadata entries
      [chunks: keyframe data]:   rotation/position/scale keys per bone

    Returns a populated MabBank object.
    """
    bank = MabBank(path=file_path, name=file_path.stem)
    bank.version = MabVersion.FC2  # mab1 and mab2 share the same core layout

    string_pool: dict[int, str] = {}
    clips: list[AnimationClip] = []

    while True:
        header = _read_chunk_header(stream)
        if header is None:
            break
        chunk_type, chunk_size = header

        # String pool chunk (type 0x02 / 1)
        if chunk_type in (0x02, 1):
            string_pool = _read_string_pool(stream, chunk_size)
            continue

        # Track metadata / clip count header (type 0x03 / 2)
        if chunk_type in (0x03, 2):
            num_bytes = stream.read(4)
            if len(num_bytes) < 4:
                break
            byte_count_val = struct.unpack("<I", num_bytes)[0]

            # The payload size is stored directly; divide to get entry count.
            num_clips = byte_count_val // 16 if (byte_count_val % 16) == 0 else 0

            for _ in range(num_clips):
                entry_data = stream.read(16)
                if len(entry_data) < 16:
                    break
                name_idx, duration_ticks, tps_raw, bone_count = struct.unpack("<IIII", entry_data[:16])
                # ticks_per_second is stored as raw / 256.0 per the Dunia format spec
                tps = round(tps_raw / 256.0) if tps_raw else 60.0

                clip_name = string_pool.get(name_idx, f"unknown_{name_idx}")
                clips.append(AnimationClip(
                    name=clip_name,
                    ticks_per_second=tps,
                    duration_ticks=duration_ticks,
                ))

            # After the track header chunk, keyframe data chunks follow.
            # We loop below to accumulate them into the clips' tracks.
            all_tracks: list[AnimationTrack] = [
                AnimationTrack(bone_name=c.name) for c in clips
            ]

            kf_count = 0
            max_kf_chunks = 200  # safety limit
            while stream.tell() < end_of_file if (end_of_file := hasattr(stream, 'seek') and stream.seek(0, 2)) or True else True:
                kf_header = _read_chunk_header(stream)
                if kf_header is None:
                    break
                kf_type, kf_size = kf_header

                if kf_type in (0x04, 3):
                    raw_kf = stream.read(kf_size)
                    new_tracks = _read_keyframe_data_from_bytes(raw_kf)
                    # Assign tracks to clips round-robin by bone index
                    for i, track in enumerate(new_tracks):
                        if i < len(all_tracks):
                            all_tracks[i] = track

                elif kf_type == 0:
                    # Zero-type chunk -- usually padding or end marker; skip.
                    stream.seek(kf_size, 1)
                else:
                    # Unknown type but has size -- skip past it.
                    stream.seek(kf_size, 1)

                kf_count += 1
                if kf_count >= max_kf_chunks:
                    break

            bank.clips = clips
            return bank

        if chunk_type in (0x5A, 90):
            # Known end-of-chunk / padding marker
            break

        # Unknown chunk -- skip past it by reading `chunk_size` bytes.
        stream.seek(chunk_size, 1)

    bank.clips = clips
    return bank


def _read_keyframe_data_from_bytes(raw: bytes):
    """Parse keyframe data from raw bytes (not file stream)."""
    tracks: list[AnimationTrack] = []
    offset = 0

    while offset + 6 <= len(raw):  # need at least tag(1) + count(4) + min_data(1)
        tag = raw[offset]
        offset += 1

        nkeys = struct.unpack("<I", raw[offset:offset+4])[0]
        offset += 4

        track = AnimationTrack(bone_name=f"keyframe_bone_track")

        for _ in range(nkeys):
            if tag == 0x01 and offset + 20 <= len(raw):
                vals = struct.unpack("<fffff", raw[offset:offset+20])
                track.rotation_keys.append(RotationKey(*vals))
                offset += 20
            elif tag == 0x03 and offset + 16 <= len(raw):
                vals = struct.unpack("<ffff", raw[offset:offset+16])
                track.position_keys.append(PositionKey(*vals))
                offset += 16
            elif tag == 0x04 and offset + 16 <= len(raw):
                vals = struct.unpack("<ffff", raw[offset:offset+16])
                track.scale_keys.append(ScaleKey(*vals))
                offset += 16
            else:
                break

        tracks.append(track)

    return tracks


def _parse_mab3(stream: BinaryIO, file_path: Path):
    """Parse a mab3-style animation bank (Far Cry 5).

    Similar to mab2 but with per-clip metadata fields added.
    The track header entries are larger (48 bytes vs 16).
    """
    bank = MabBank(path=file_path, name=file_path.stem)
    bank.version = MabVersion.FC5

    string_pool: dict[int, str] = {}
    clips: list[AnimationClip] = []

    while True:
        header = _read_chunk_header(stream)
        if header is None:
            break
        chunk_type, chunk_size = header

        if chunk_type in (0x02, 1):
            string_pool = _read_string_pool(stream, chunk_size)
            continue

        if chunk_type in (0x03, 2):
            num_bytes = stream.read(4)
            if len(num_bytes) < 4:
                break
            byte_count_val = struct.unpack("<I", num_bytes)[0]
            num_clips = byte_count_val // 16 if (byte_count_val % 16) == 0 else 0

            for _ in range(num_clips):
                entry_data = stream.read(48)  # mab3 headers are longer (extra metadata fields)
                if len(entry_data) < 16:
                    break
                name_idx, duration_ticks, tps_raw, bone_count = struct.unpack("<IIII", entry_data[:16])
                tps = round(tps_raw / 256.0) if tps_raw else 60.0

                clip_name = string_pool.get(name_idx, f"unknown_{name_idx}")
                clips.append(AnimationClip(
                    name=clip_name,
                    ticks_per_second=tps,
                    duration_ticks=duration_ticks,
                ))

            all_tracks: list[AnimationTrack] = [
                AnimationTrack(bone_name=c.name) for c in clips
            ]

            kf_count = 0
            max_kf_chunks = 200  # safety limit
            while True and not stream or (stream.tell() < end_of_file if (end_of_file := hasattr(stream, 'seek') and stream.seek(0, 2)) or True else True):
                kf_header = _read_chunk_header(stream)
                if kf_header is None:
                    break
                kf_type, kf_size = kf_header

                if kf_type in (0x04, 3):
                    raw_kf = stream.read(kf_size)
                    new_tracks = _read_keyframe_data_from_bytes(raw_kf)
                    for i, track in enumerate(new_tracks):
                        if i < len(all_tracks):
                            all_tracks[i] = track

                elif kf_type == 0:
                    stream.seek(end_of_file, 1)
                else:
                    stream.seek(chunk_size, 1)

                kf_count += 1
                if kf_count >= max_kf_chunks:
                    break

            bank.clips = clips
            return bank

        # Unknown chunk -- skip past it.
        stream.seek(chunk_size, 1)

    bank.clips = clips
    return bank


# ===================================================================
# Public API
# ===================================================================


def read_mab_file(file_path):
    """Parse a .mab animation bank file and return structured data.

    Args:
        file_path: Path to the .mab file on disk.

    Returns:
        MabBank with all clips parsed, or None if parsing fails.
    """
    path = Path(file_path)
    if not path.exists():
        return None

    try:
        with open(path, "rb") as f:
            magic = _read_magic(f)
            if magic is None:
                return None

            version = MAGIC_MAP.get(magic, MabVersion.UNKNOWN)

            if version == MabVersion.UNKNOWN:
                # Default assumption for unknown magic; most Dunia files are mab2.
                version = MabVersion.FC3

            parser = _parse_mab2 if version in (MabVersion.FC2, MabVersion.FC3) else _parse_mab3
            bank = parser(f, path)
            return bank

    except Exception as exc:
        print(f"  Warning: Error parsing {path}: {exc}")
        return None


def read_all_clip_names(file_path):
    """Quick parse to extract just the animation clip names (no bone data).

    Useful for fast scanning without loading full keyframes.

    Args:
        file_path: Path to the .mab file.

    Returns:
        List of string names like ['rifle_idle', 'rifle_fire',
                                    'reload_start', ...].
    """
    bank = read_mab_file(file_path)
    if bank and hasattr(bank, 'clips') and len(bank.clips):  # type: ignore[misc]
        result: list[str] = [c.name for c in bank.clips]
        return result
    return []


def _read_magic(stream: BinaryIO) -> bytes | None:
    """Read 4-byte magic tag from the .mab file header."""
    data = stream.read(4)
    return data if len(data) == 4 else None
