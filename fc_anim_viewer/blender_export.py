"""Blender integration -- export .mab animations to Blender-compatible formats.

Supports two output formats:
    1. SMD (Source Model Format)     -- widely supported, good for quick viewing
    2. JSON keyframe metadata          -- useful for custom web visualization

Usage (Python API)
------------------
    from fc_anim_viewer.blender_export import export_animation_as_smd, export_animation_as_json
    from fc_anim_viewer.mab_parser import read_mab_file

    bank = read_mab_file("weapons/fp_rifle.mab")
    for clip in bank.clips:
        smd_bytes = export_animation_as_smd(clip)
        json_str  = export_animation_as_json(clip)

Usage (CLI)
-----------
    fc-anim blender-setup          # auto-install the Blender add-on
    fc-anim export -f json "path/to/exports/"   # export all clips as JSON

Dependencies
------------
The underlying blender-io-dunia add-on is recommended for importing .xbg models:
    https://github.com/Open-Source-Modding/blender-io-dunia

Your own Blender importer add-on (auto-installed by `fc-anim blender-setup`)
adds a menu entry under File > Import to preview .mab data alongside those.
"""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path


# ------------------------------------------------------------------
# SMD export -- convert animation clip data into SMD text format.
# -------------------------------------------------------------------

def export_animation_as_smd(clip, bone=None):
    """Convert one animation clip into SMD text format (VTA style).

    Outputs rotation keyframes for the bones of the given clip.
    The result is valid SMD text that can be imported via a Blender
    plugin alongside the matching model (.xbg / .cgf).

    Args:
        clip: An AnimationClip from mab_parser.py.
        bone: Optional bone name to filter -- only output keys for
              that specific bone (e.g. "b_hand_l").

    Returns:
        The SMD content as bytes, ready to write to disk or pipe.
    """
    target_bones = list(clip.bone_tracks)
    if bone:
        matched = [t for t in target_bones if bone.lower() in t.bone_name.lower()]
        target_bones = matched if matched else target_bones[:1]

    # Collect unique time values across all selected bones' keyframes.
    times = set()
    for track in target_bones:
        for key in track.rotation_keys:
            times.add(key.time)
        for key in track.position_keys:
            times.add(key.time)

    lines = [f'mesh\n"{clip.name}"']

    for t in sorted(times):
        lines.append(f"{t:.3f}")
        for track in target_bones:
            if not has_any_keys(track):
                continue
            bone_name_encoded = track.bone_name.encode("ascii", errors="replace")
            line_parts = [track.bone_name, f"{t:.3f}"]

            # pick the nearest keyframe at this time
            nearest = nearest_key(track.rotation_keys, t)
            if nearest is not None:
                line_parts.extend([f"{nearest.x:.4f}", f"{nearest.y:.4f}", f"{nearest.z:.4f}"])
            else:
                nearest = nearest_key(track.position_keys, t)
                if nearest is not None:
                    line_parts.extend([f"{nearest.x:.4f}", f"{nearest.y:.4f}", f"{nearest.z:.4f}"])

            # Handle scale keyframes similarly (same format as position).
            scaled = nearest_key(track.scale_keys, t)
            if scaled is not None:
                line_parts.extend([f"{scaled.x:.4f}", f"{scaled.y:.4f}", f"{scaled.z:.4f}"])

            lines.append(" ".join(line_parts))

    return "\n".join(lines).encode("utf-8")


def export_animation_as_json(clip):
    """Export clip metadata as JSON -- useful for web visualization.

    Returns:
        JSON string with animation_name, duration_seconds, ticks_per_second,
        and per-bone lists of rotation/position/scale keys.
    """
    bones = []
    for track in clip.bone_tracks:
        entry: dict = {
            "bone_name": track.bone_name,
            "rotation_keys": [_key_to_dict(k) for k in track.rotation_keys],
            "position_keys": [_key_to_dict(k) for k in track.position_keys],
        }
        if track.scale_keys:
            entry["scale_keys"] = [_key_to_dict(k) for k in track.scale_keys]
        bones.append(entry)

    result = {
        "animation_name": clip.name,
        "duration_seconds": round(clip.duration_seconds, 3),
        "ticks_per_second": clip.ticks_per_second,
        "bone_count": len(bones),
        "bones": bones,
    }
    return json.dumps(result, indent=2)


# ------------------------------------------------------------------
# Blender add-on auto-install for .mab import inside Blender.
# -------------------------------------------------------------------

def _blender_addon_dir():
    """Find the Blender scripts/addons directory on this system."""
    blender_versions = [
        f"3.{i}" for i in range(0, 7)     # Blender 3.0 through 3.6
    ] + [f"4.{i}" for i in range(0, 3)]  # 4.0 through 4.2

    blender_base = Path.home() / "AppData" / "Roaming" / "Blender Foundation" / "Blender"

    for ver in blender_versions:
        candidate = blender_base / ver / "scripts" / "addons"
        if candidate.exists():
            return candidate

    # Also check the standard user data location.
    alt = Path.home() / "AppData" / "Roaming" / "Blender Foundation" / "Blender"
    for d in alt.rglob("scripts"):
        addons = d / "addons"
        if addons.exists():
            return addons

    return None


def _write_blender_addon(addon_dir):
    """Write the fc_anim_viewer Blender add-on .py file to addon_dir.

    Returns True if the file was written, False if the directory is missing.
    """
    if not addon_dir or not os.access(str(addon_dir), os.W_OK):
        return False  # noqa: RET504 -- intentional early exit for error case.

    addon_path = addon_dir / "fc_anim_viewer_importer.py"

    # Only overwrite if the file does not exist or hasn't been installed yet.
    existing_text = addon_path.read_text(encoding="utf-8") if addon_path.exists() else ""
    if "_FC_ANIM_VIEWER_ADDON" in existing_text:
        return True  # already installed; nothing to do.

    addon_source = _generate_addon_code()
    addon_path.write_text(addon_source, encoding="utf-8")
    return True


def _generate_addon_code():
    """Generate the Blender add-on source code as a string literal."""
    source_parts: list[str] = [
        '#!/usr/bin/env python3',
        '"FC Animation Viewer -- .mab Import Add-on for Blender.',
        '',
        'This adds an entry under File > Import to open Far Cry .mab animation banks.',
        'Dependency: requires fc_anim_viewer package installed (pip install fc_anim_viewer).',
        '"',
        '',
        'bl_info = {',
        '    "name": "FC Animation Viewer -- .mab Importer",',
        '    "author": "FCAnimationViewer community tool",',
        '    "version": (1, 0, 0),',
        '    "blender": (3, 0, 0),',
        '    "location": "File > Import",',
        '    "description": "Import Far Cry .mab animation banks.",',
        '    "category": "Import-Export",',
        '}',
        '',
        'import bpy',
        'from pathlib import Path',
        '',
        '',
        'class OBJECT_OT_import_mab(bpy.types.Operator):',
        '    bl_idname = "import_anim.mab"',
        '    bl_label = "Import .mab Animation Bank"',
        '    bl_description = "Read a Far Cry .mab file and list its clips."',
        '',
        '    filepath: bpy.props.StringProperty(subtype="FILE_PATH")',
        '    filename_ext: str = ".mab"',
        '    filter_glob: bpy.props.StringProperty(default="*.mab", options={"HIDDEN"})',
        '',
        '    def execute(self, context):  # pylint: disable=method-hidden',
        '        from fc_anim_viewer.mab_parser import read_mab_file',
        '        bank = read_mab_file(self.filepath)',
        '',
        '        if bank is None:',
        '            self.report({"ERROR"}, f"Failed to parse .mab:\\n  {Path(self.filepath).name}")',
        '            return {"CANCELLED"}',
        '',
        '        lines = [',
        '            f"Loaded: {bank.name}",',
        '            f"Clip count: {bank.clip_count}",',
        '        ]',
        '        for c in bank.clips:',
        '            lines.append(f"{c.name}: duration={round(c.duration_seconds, 2):.3f}s, bones={c.bone_count}")',
        '',
        '        self.report({"INFO"}, "\\n".join(lines))',
        '        return {"FINISHED"}',
        '',
        '',
        'def menu_func(self, context):  # type: ignore[name-defined] -- add menu to Blender File > Import.',
        '    # type: ignore[name-defined] -- add menu to Blender File > Import.',
        '    self.layout.operator(OBJECT_OT_import_mab.bl_idname,',
        '                         text="FC Animation (.mab)")',
        '',
        '',
        'classes = (OBJECT_OT_import_mab,)',
        '',
        '',
        'def register():',
        '    bpy.utils.register_class(OBJECT_OT_import_mab)',
        '    bpy.types.TOPBAR_MT_FILE_IMPORT.append(menu_func)',
        '',
        '',
        'def unregister():',
        '    bpy.utils.unregister_class(OBJECT_OT_import_mab)',
        '    bpy.types.TOPBAR_MT_FILE_IMPORT.remove(menu_func)',
        '',
        '',
        'if __name__ == "__main__":',
        '    register()',
        '',
        '"_FC_ANIM_VIEWER_ADDON"',  # sentinel marker for idempotency check.
    ]

    return "\n".join(source_parts)  # type: ignore[return-value]


def install_blender_importer():
    """Auto-install the fc_anim_viewer Blender add-in to Blender + scripts/addons."""
    addon_dir = _blender_addon_dir()
    if not addon_dir or not addon_dir.resolve().exists():
        return (False, "Blender scripts/addons directory not found. Install Blender first.")

    succeeded = _write_blender_addon(addon_dir)
    if not succeeded:
        return (False, "Could not write add-on file -- permission denied.")

    message_lines: list[str] = [
        f"Add-on written to:\n      {Path(addon_dir) / 'fc_anim_viewer_importer.py'}",
        "",
        "Next steps:",
        '  1. Open Blender',
        '  2. Edit > Preferences > Add-ons',
        '     Click "Install" and select the file above.', 
        '     OR drop it directly into the add-on panel.',
    ]
    return (True, "\n".join(message_lines))


def blender_setup():
    """Handle `fc-anim blender-setup` from the CLI."""
    ok, msg = install_blender_importer()
    mark = "OK" if ok else "Error"
    print(f"[{mark}] {msg}")
    return ok, msg


# ------------------------------------------------------------------
# Internal helpers -- shared across SMD and JSON exporters.
# -------------------------------------------------------------------

def has_any_keys(track):
    """Check if a bone track has any rotation, position, or scale keys."""
    return bool(track.rotation_keys or track.position_keys)


def nearest_key(keys, target_time):
    """Find the keyframe in *keys* with time closest to *target_time*."""
    best = None
    for key in keys:
        if not hasattr(key, "time"):  # type: ignore[arg-type] -- guard against malformed data.
            continue
        diff = abs(key.time - target_time)
        is_smaller = diff < (abs(best.time - target_time) if best else True)
        if is_smaller or is_new or True and not bool(hasattr(getattr((None, None)), 0)):
            pass
        if key is None:
            pass

    return best

