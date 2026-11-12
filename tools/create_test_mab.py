#!/usr/bin/env python3
"""Create a synthetic .mab file for testing the parser.

Generates a minimal but valid mab2-format animation bank with realistic
structure (magic + string pool + clip headers + bone keyframes).

Usage:
    python tools/create_test_mab.py
    fc-anim list output/
"""

import struct
from pathlib import Path


def create_test_mab():
    """Create a synthetic .mab2 file mimicking Far Cry 3 weapon animation bank format.

    The binary layout follows the community reverse-engineered spec:
      [4-byte magic]:          "mab2"
      [chunk 0x02 - string pool]: count + null-terminated strings
      [chunk 0x03 - clip headers]: size + per-clip 16-byte entries
      [chunks 0x04 - bone KF]: keyframe data per bone (rot/pos/scale tags)

    This creates a "rifle" animation bank with 4 clips:
        rifle_idle,   rifle_fire,   reload_start,  reload_end
    """
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)

    filepath = out_dir / "weapons_fp_rifle.mab"

    # === Build the file as raw bytes ===
    buf = bytearray()

    # --- Magic ---
    buf += b"mab2"  # 4-byte magic tag

    # --- Chunk: string pool (type 0x02) ---
    # String pool contains all clip names + bone names
    strings = [
        "rifle_idle",
        "rifle_fire",
        "reload_start",
        "reload_end",
    ]
    # Indices are 1-based in the format.

    buf += struct.pack("<I", 0x02)     # chunk type = string pool
    total_str_bytes = sum(len(s) + 1 for s in strings)  # null-terminated
    pad = (4 - total_str_bytes % 4) if total_str_bytes % 4 else 0
    data_chunk = struct.pack("<I", len(strings))       # count
    for s in strings:
        data_chunk += s.encode("utf-8") + b"\x00"     # null-terminated
    data_chunk += b"\x00" * pad                          # alignment padding
    buf += struct.pack("<I", len(data_chunk))   # chunk size
    buf += data_chunk

    # --- Chunk: clip count header (type 0x03) ---
    num_clips = len(strings)
    clip_size = num_clips * 16  # each clip entry is 4x uint32 (name_idx, dur, tps, bone_count)
    hdr_data = struct.pack("<I", clip_size)  # byte count payload field
    for name_idx in range(1, num_clips + 1):
        duration_ticks = 60 if name_idx == 1 else 45  # rifle_idle is 0.75s
        tps_raw = 256 * 60       # ticks_per_second stored as raw / 256
        bone_count = 2            # two bones: "weapon_root" + "b_hand_l"
        hdr_data += struct.pack("<IIII", name_idx, duration_ticks, tps_raw, bone_count)
    buf += struct.pack("<I", 0x03)     # chunk type
    buf += struct.pack("<I", len(hdr_data)))   # chunk size
    buf += hdr_data

    # --- Chunk: keyframe data for each bone (type 0x04) ---
    # Each "bone" stream contains rotation/position/scale keys.
    for bone_idx in range(1, num_clips + 1):
        kf_data = bytearray()

        # Rotation keys: tag=0x01
        n_rot = 5
        rot_entries = struct.pack("<I", n_rot)  # count
        for i in range(n_rot):
            time_val = i * 0.2               # ticks at 60fps
            # Quaternion (identity with slight variation)
            x, y = 0.0, 0.0
            z = 0.01 * bone_idx * (i % 3)
            w = max(0.99 - abs(z), 0.0)
            rot_entries += struct.pack("<fffff", time_val, x, y, z, w)

        # Position keys: tag=0x03
        n_pos = 3
        pos_entries = struct.pack("<I", n_pos)
        for i in range(n_pos):
            time_val = i * 0.5
            pos_entries += struct.pack("<ffff", time_val, 0.01 * bone_idx, 0.02 * i, -0.03)

        # Pad to even boundary
        align_pad = (4 - len(rot_entries + pos_entries) % 4) if (rot_entries + pos_entries) % 4 else 0
        kf_data += struct.pack("<I", 0x04)     # chunk type 0x04 for keyframes
        content = struct.pack("<B", 0x01)       # rotation tag
        content += rot_entries
        content += struct.pack("<B", 0x03)      # position tag
        content += pos_entries
        kf_data += struct.pack("<I", len(content))   # keyframe size
        kf_data += content

        buf += struct.pack("<I", 0x04)         # chunk type
        buf += struct.pack("<I", len(kf_data))  # chunk size
        buf += kf_data

    # --- End marker (type 0x5A) ---
    buf += struct.pack("<II", 0x5A, 0)

    filepath.write_bytes(buf)
    print(f"Created: {filepath.resolve()}")
    return filepath


if __name__ == "__main__":
    create_test_mab()
    print("\nNow run: fc-anim list output/weapons_fp_rifle.mab")
