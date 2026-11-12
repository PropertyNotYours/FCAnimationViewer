#!/usr/bin/env python3
"""FC Animation Viewer — read and list Far Cry gun animations.

Parses .mab (Animation Bank) files from Far Cry 2 through Far Cry 5+.
Stands on the community's reverse-engineering work:
  • buu342/PY-DuniaAnimationExtractor  – raw keyframe extraction logic
  • Open-Source-Modding/blender-io-dunia – Blender import patterns

Usage (Python API):
    from fc_anim_viewer.mab_parser import read_mab_file
    bank = read_mab_file("path/to/weapons/fp_assault_rifle.mab")
    for clip in bank.clips:
        print(f"  {clip.name}: {clip.bone_count} bones, "
              f"{clip.duration_seconds:.2f}s")

Usage (CLI):
    fc-anim list "C:/Games/FC3_extracted"       # scan an entire folder
    fc-anim list "file.mab"                      # show one file
    fc-anim find -n "m4a1" "C:/Games/FC3"        # search by gun name

See docs/SETUP.md for step-by-step beginner setup.
"""

__version__ = "0.1.0"
