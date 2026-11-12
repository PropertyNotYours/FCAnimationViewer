# .mab Animation Bank Format Reference

This documents what we know about the `.mab` format from community reverse-engineering.
We implement this in `mab_parser.py`.

## Overview

`.mab` = **M**otion **A**nimation **B**ank — a collection of named animation clips
Each clip has keyframes for bone rotations, translations, and scales over time.

## Chunk-Based Structure

The format uses a chunk-oriented layout: each section starts with a header describing
what follows (type code + size), then the raw data bytes.

```
[Chunk 0] ── magic/version header ──→ "mab1" or "mab2" or similar
[Chunk 1] ── string pool (all names)
[Chunk 2] ── bone name lookup table
[Chunk 3] ── animation track headers (N tracks)
[Chunk N] ── per-track keyframe data
```

### Chunk Header Format

Each chunk starts with:
| Offset | Size | Type | Description |
|--------|------|------|-------------|
| 0 | 4 bytes | uint32 | Chunk type ID (e.g., 1 = animation header, 2 = keyframes) |
| 4 | 4 bytes | uint32 | Chunk size in bytes (of the data payload) |

### Known Chunk Types

| Type ID | Description | Contains |
|---------|-------------|----------|
| 0x01 | Version/magic header | Magic string + version number |
| 0x02 | Animation track descriptions | Per-clip metadata (name index, start/end frame, bone IDs) |
| 0x03 | Bone/track count | Total bones, total tracks used by this clip |
| 0x04–0x06 | Keyframe data | Position keys, rotation keys, scale keys |
| 0xFF (or similar) | End of clip marker | Signals end of animation data |

### Track/Clip Structure (inside chunk type 2)

Each track entry within a chunk:
| Offset | Size | Description |
|--------|------|-------------|
| 0 | uint32 | Animation name index into string pool |
| 4 | uint32 | Duration in ticks |
| 8 | uint32 | Ticks per second (often 60 or 100) |
| 12 | uint32 | Bone/tracks count for this clip |
| 16 | uint32 | Offset to first bone reference array |

### Keyframe Data Format

Rotation keys use **quaternion** format (x, y, z, w floats):
```
[time: f32] [quaternion x: f32] [y: f32] [z: f32] [w: f32]  = 20 bytes per key
```

Position keys use **vector** format (x, y, z floats):
```
[time: f32] [pos x: f32] [y: f32] [z: f32]  = 16 bytes per key
```

Scale keys use **vector** format with time:
```
[time: f32] [scale x: f32] [y: f32] [z: f32]  = 16 bytes per key
```

## Dunia Version Differences

### Version 1 (Far Cry 2 / Early Dunia)
- Track header is shorter (~12 bytes each)
- No scale keyframes (only position + rotation)
- String pool format differs slightly

### Version 2 (Far Cry 3 / FC4)
- Standard track header with full name/duration/ticks/bone_count
- Has all three keyframe types: pos, rot, scale
- Uses `mab2` magic tag

### Version 3 (Far Cry 5 / Dunia 3)
- Added extra metadata flags per clip
- Compressed quaternion encoding in some files
- FC6 is a known blocker — format may have changed again

## Game-Specific Notes: Weapon Animations

Weapon (.gdn or fp_) animation banks contain two kinds of data:

1. **First-person gun animations**: Hand bones moving the weapon (idle sway, fire recoil, reload reach)
2. **Third-person model animations**: The actual mesh's local animation (slide cycling, bolt movement)

The gun model name is typically stored in the animation string name or alongside it
as part of a `GDN` asset reference.
