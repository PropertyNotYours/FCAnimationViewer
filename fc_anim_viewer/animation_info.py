"""Data model for Far Cry .mab animation bank data.

Each .mab file is an "Animation Bank" containing multiple named clips.
This module defines the data structures we use to represent it in memory.

Usage
-----
    from fc_anim_viewer.animation_info import MabBank, AnimationClip
    # These are the classes mab_parser.py populates when it reads a .mab file.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path


# ---------------------------------------------------------------------------
# Supported .mab versions (magic tags)
# ---------------------------------------------------------------------------

class MabVersion(IntEnum):
    """Known .mab format versions across Dunia titles."""
    UNKNOWN = 0
    FC2     = 1   # Far Cry 2 — early Dunia
    FC3     = 2   # Far Cry 3 / FC4 — Dunia 2 (most common)
    FC5     = 3   # Far Cry 5 — Dunia 3


# Map magic strings to versions
MAGIC_MAP: dict[bytes, MabVersion] = {
    b"mab1": MabVersion.FC2,
    b"mab2": MabVersion.FC3,
    b"mab3": MabVersion.FC5,
}


# ---------------------------------------------------------------------------
# Keyframe structs
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class RotationKey:
    """A single quaternion rotation keyframe for a bone."""
    time: float  # time in ticks
    x: float     # quaternion components (normalized)
    y: float
    z: float
    w: float


@dataclass(slots=True)
class PositionKey:
    """A single position translation keyframe for a bone."""
    time: float
    x: float
    y: float
    z: float


@dataclass(slots=True)
class ScaleKey:
    """A single scale keyframe for a bone."""
    time: float
    x: float
    y: float
    z: float


# ---------------------------------------------------------------------------
# Per-bone track (a bone that has animated data in this clip)
# ---------------------------------------------------------------------------

@dataclass
class AnimationTrack:
    """All keyframes for one bone within a single animation clip."""
    bone_name: str
    rotation_keys: list[RotationKey] = field(default_factory=list)
    position_keys: list[PositionKey] = field(default_factory=list)
    scale_keys: list[ScaleKey] = field(default_factory=list)

    @property
    def has_rotation(self) -> bool:
        return len(self.rotation_keys) > 0

    @property
    def has_translation(self) -> bool:
        return len(self.position_keys) > 0

    @property
    def has_scale(self) -> bool:
        return len(self.scale_keys) > 0


# ---------------------------------------------------------------------------
# Single named animation clip
# ---------------------------------------------------------------------------

@dataclass
class AnimationClip:
    """One named animation inside a .mab bank (e.g. 'rifle_idle', 'reload_start')."""
    name: str                       # clip name, e.g. "rifle_idle"
    ticks_per_second: float = 60.0  # speed of the tick clock
    duration_ticks: float = 0.0     # total animation length in ticks
    bone_tracks: list[AnimationTrack] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if self.ticks_per_second <= 0:
            return 0.0
        return self.duration_ticks / self.ticks_per_second

    @property
    def bone_count(self) -> int:
        return len(self.bone_tracks)


# ---------------------------------------------------------------------------
# Full .mab bank — may contain multiple clips
# ---------------------------------------------------------------------------

@dataclass
class MabBank:
    """A complete .mab animation bank file."""
    path: Path
    name: str                        # friendly display name (stem of filename)
    version: MabVersion = MabVersion.UNKNOWN
    clips: list[AnimationClip] = field(default_factory=list)

    @property
    def clip_count(self) -> int:
        return len(self.clips)

    @property
    def first_clip_name(self) -> str | None:
        return self.clips[0].name if self.clips else None

    @property
    def max_duration_seconds(self) -> float:
        """Duration of the longest animation clip in this bank."""
        if not self.clips:
            return 0.0
        return max(c.duration_seconds for c in self.clips)


# ---------------------------------------------------------------------------
# Scan result — what we gather when scanning a game folder
# ---------------------------------------------------------------------------

@dataclass
class GameScanResult:
    """Result of scanning a game root folder."""
    game_path: Path
    mab_files_by_model: dict[str, list[Path]] = field(default_factory=dict)
    total_mab_files: int = 0
    total_clips: int = 0
    models_found: list[str] = field(default_factory=list)

    def summary_text(self) -> str:
        lines = [
            f"\n{'=' * 60}",
            f"Scan result for: {self.game_path}",
            f"  .mab files found : {self.total_mab_files}",
            f"  total clips      : {self.total_clips}",
            f"  unique models    : {len(self.models_found)}",
            f"{'=' * 60}",
        ]
        for model in sorted(self.models_found)[:30]:
            paths = self.mab_files_by_model.get(model, [])
            lines.append(f"  {model}: {len(paths)} bank file(s)")
        if len(self.models_found) > 30:
            extra = len(self.models_found) - 30
            lines.append(f"  ... and {extra} more models")
        return "\n".join(lines)
