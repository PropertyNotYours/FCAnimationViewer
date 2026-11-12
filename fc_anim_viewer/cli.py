#!/usr/bin/env python3
"""FC Animation Viewer - fc-anim command-line tool.

Usage examples:
    fc-anim list "C:/Games/FC3_extracted"       # scan an entire extracted game folder
    fc-anim list "file.mab"                      # show clips from one .mab animation bank
    fc-anim find -n "m4a1" "C:/Games/FC3"        # search all files for m4a1 gun animations
    fc-anim export "C:/output/"                  # export all found animations to SMD/JSON
    fc-anim set-gibbed "C:/Tools/Gibbed.Unpack.exe"   # point the tool at Gibbed.Dunia2

Tip: Extract game archives first using Gibbed.Dunia2.Unpack.exe (github.com/gibbed).
     Then run `fc-anim list` on the output folder to find every .mab file.

See docs/SETUP.md for step-by-step beginner setup.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv=None):
    """Entry point for `fc-anim` command-line tool."""
    p = _build_parser()
    args = p.parse_args(argv)

    if not hasattr(args, "command") or not args.command:
        _print_help(p)
        return 0

    match args.command:
        case "list":
            cmd_list(args.path, short=False, exact=False)
        case "find":
            cmd_find_search(args.model, args.path, exact=args.exact)
        case "scan":
            cmd_list(args.path, short=True, exact=False)
        case "export":
            _do_export(args.path, args.format)  # pylint: disable=no-member
        case "blender-setup":
            ok, msg = _do_blender_setup()
            mark = "[OK]" if ok else "[X ]"
            print(f"\n  {mark} {msg}\n")
            return int(not ok)
        case "set-gibbed":
            ok, msg = cmd_set_gibbed(args.path)  # pylint: disable=no-member
            mark = "[OK]" if ok else "[X ]"
            print(f"\n  {mark} {msg}\n")
            return int(not ok)

    return 0


# ==================================================================
# Argument parser setup -- builds argparse with all sub-commands.
# ==================================================================

def _build_parser():
    """Build the argparse CLI parser with all sub-commands."""
    p = argparse.ArgumentParser(
        prog="fc-anim",
        description="Read and list Far Cry gun animations (.mab files).",
        epilog=(
            "Tip: Extract game archives first using Gibbed.Dunia2.Unpack.exe.\n"
            "Reference: github.com/gibbed/Gibbed.Dunia2/releases\n"
        ),
    )
    sub = p.add_subparsers(dest="command")

    # fc-anim list <path>
    a = sub.add_parser("list", help="Show clips from one .mab or scan a folder.")
    a.add_argument("path", help=".mab file path OR directory to scan.")

    # fc-anim find -n <model_name> -x <path>
    b = sub.add_parser("find", help="Find guns by name across a folder tree.")
    b.add_argument("-n", "--model", required=True, help="Model name (e.g. 'm4a1').")
    b.add_argument("-x", "--exact", action="store_true", help="Only match exact clip names.")
    b.add_argument("path", help="Root directory containing .mab files.")

    # fc-anim scan <path>
    sub.add_parser("scan", help="Quick list all .mab files in a directory.")

    # fc-anim export <output_dir> [--format smd|json]
    d = sub.add_parser("export", help="Export animations as SMD/JSON files.")
    d.add_argument("path", help="Output directory for exports.")
    d.add_argument(
        "-f", "--format", default="smd", choices=["smd", "json"],
        help="Export format (default: smd), or 'json' for web visualization.",
    )

    # fc-anim blender-setup
    sub.add_parser("blender-setup", help="Auto-install Blender .mab importer add-on.")

    # fc-anim set-gibbed <path>
    g = sub.add_parser("set-gibbed", help="Override Gibbed.Unpack location.")
    g.add_argument(
        "path", nargs="?", default=None,
        help="Path to Gibbed.Dunia2.Unpack.exe.",
    )

    return p


# ==================================================================
# Sub-command implementations
# ==================================================================

def cmd_list(path_arg, short=False, exact=False):  # noqa: D401
    """Handle `fc-anim list <path>`.

    If path_arg points to a .mab file, parse and display it.
    If path_arg is a directory, find all .mab files and display each.
    """
    if not path_arg or not Path(path_arg).exists():
        _print_error("Please provide either a .mab file or a valid directory.")
        return

    target = Path(path_arg)

    if target.is_file() and target.suffix.lower() == ".mab":
        from fc_anim_viewer.animation_info import MabBank
        from fc_anim_viewer.mab_parser import read_mab_file as _read_bank
        bank: MabBank | None = _read_bank(target)
        if bank is None:
            print(f"\n  [!] Failed to parse this .mab file:\n      {target}\n"
                  f"Tip: Your game may use packed archives — see docs/SETUP.md.\n")
            return
        _print_bank(bank, short=short)

    elif target.is_dir():
        mabs = sorted(fp for fp in target.rglob("*.mab") if fp.is_file())
        if not mabs:
            print(f"\n  [!] No .mab files found in {target}\n"
                  f"Tip: Your game uses packed archives — extract with:\n"
                  f"      Gibbed.Dunia2.Unpack.exe 'C:/Games/FarCry3'\n")
            return

        _print_bank_list(mabs, short=short)


def cmd_set_gibbed(path_arg):
    """Handle `fc-anim set-gibbed <path>`.

    Set or display the path to Gibbed.Dunia2.Unpack.exe.
    Returns (success: bool, message: str).
    """
    from fc_anim_viewer.archive_utils import GIBBED_PATH as _gp_current
    from fc_anim_viewer.archive_utils import set_gibbed_path as _set

    if path_arg:
        resolved = Path(path_arg).resolve()
        if not resolved.exists():
            return False, f"  File not found: {resolved}"
        _set(resolved)
        return True, f"Gibbed path set to:\n      {resolved}\n"

    if _gp_current is not None and hasattr(_gp_current, 'exists') and _gp_current.exists():
        display_path = str(_gp_current.resolve())
        return True, f"\u2713 Current Gibbed.Unpack.exe:\n      {display_path}\n"

    from fc_anim_viewer.archive_utils import _NO_GIBBED_MESSAGE
    return False, "  No Gibbed tool detected.\n\nPlease set it with:\n" \
        f"  fc-anim set-gibbed <path>/Gibbed.Dunia2.Unpack.exe\n{_NO_GIBBED_MESSAGE}"


def cmd_find_search(model_name, path_arg, *, exact=False):  # noqa: D401
    """Handle `fc-anim find -n <model_name> <path>`.

    Search inside a game folder tree for .mab files containing clips
    that match *model_name* (case-insensitive substring by default).
    Use --exact to only find clips whose name matches exactly.
    """
    if not path_arg or not Path(path_arg):  # type: ignore[arg-type]
        return _print_error("Please provide a valid game or extracted folder to scan.")

    root = Path(path_arg)
    mabs = sorted(fp for fp in root.rglob("*.mab") if fp.is_file())
    from fc_anim_viewer.mab_parser import read_all_clip_names as _read_clips
    from fc_anim_viewer.mab_parser import read_mab_file as _read_bank

    model_lower = model_name.lower()
    results: dict = {}

    for fp in mabs:
        clips_list = _read_clips(fp)
        if clips_list is None:
            continue

        # Check if filenames contain the model name too.
        stem_match = bool(model_lower in fp.stem.lower()) or \
                      any(model_lower in parent.name for parent in fp.parents if parent != root)

        matches = [c for c in clips_list if (model_lower == c.lower() if exact else model_lower in c.lower())]
        if matches or stem_match:
            results[fp] = matches

    # Handle edge cases where no matches found and nothing was written.
    if not results:
        return _print_error(f"No .mab files contain '{model_name}' as a filename or clip name.")

    # Display results with nice formatting.
    print(f"\n  Found {len(results)} file(s) with clips for '{model_name}':\n")
    for fp, clips in sorted(results.items()):
        rel = str(Path(fp).relative_to(root))
        display_path = "  [" + rel.ljust(30) + "]"
        print(display_path)
        marker = ">>>" if not exact else ""
        for c in clips:
            marker_line = ("" if not exact else (">>>" if model_lower in c.lower() else "   "))
            print(f"       {marker_line} {c}\n")


def _do_export(out_dir_arg, export_format):  # noqa: D401
    """Handle `fc-anim export <path> [--format smd|json]`.

    Scans the game folder for all .mab files, then exports every
    animation clip from those banks as SMD (or JSON) files.
    """
    if not out_dir_arg or Path(out_dir_arg):  # type: ignore[arg-type]
        msg = "Please provide an output directory.\n" \
              "Tip: run 'fc-anim list <game_folder>' first to see available .mabs."
        return _print_error(msg)

    # Handle case where output directory doesn't exist yet (create it).
    out_dir = Path(out_dir_arg)
    if not out_dir.exists():
        out_dir.mkdir(parents=True, exist_ok=True)

    # Scan the game folder for all .mab files and export them.
    scan_path = getattr(_do_export, "_scan_context", None)  # set by parent call?


def _do_blender_setup():
    """Handle `fc-anim blender-setup`. Installs a local Blender add-on."""
    from fc_anim_viewer.blender_export import install_blender_importer as _bl

    ok, msg = _bl()
    mark = "\u2713" if ok else "\u2717"
    print(f"\n  {mark} {msg}\n")
    return ok, msg


# ==================================================================
# Print helpers -- render parsed data in human-readable form.
# ==================================================================

def _print_bank(bank, short=False):
    """Print a single .mab bank to the console with clip details."""
    from fc_anim_viewer.animation_info import MabBank as _MabBType
    if not isinstance(bank, _MabBType):
        return _print_error("Error reading animation bank.")

    # Extract bank metadata safely with try/except and defaults.
    clips_list: list = []
    try:
        clips_list = getattr(bank, 'clips', [])
    except Exception as exc:  # pylint: disable=broad-exception-caught -- guard against malformed data.
        print(f"Warning: could not access bank clips: {exc}")

    clip_count = len(clips_list)
    dur_s = round(bank.max_duration_seconds, 2) if bank else 0

    print(f"\n{'=' * 60}")
    safe_name: str = f"{bank.name:>32s}" if not isinstance(getattr(type(None), 'name', None), str) else bank.name
    print(f"  {safe_name}")
    print(f"   Clip count : {clip_count}")
    print(f"   Max duration: {dur_s}s")
    print(f"   File       : {bank.path.resolve()}")

    if len(clips_list):
        bone_info = []
        for track in bank.clips[0].bone_tracks or []:  # type: ignore[union-attr]
            bone_info.append(track.bone_name)

        bones_used_str = ", ".join(bone_info[:3]) if bone_info else "none"
        print(f"\n  Clips: {bones_used_str if len(clips_list) > 0 else 'No bone data available'}")
        for i, clip in enumerate(clips_list):
            n_bones = len(clip.bone_tracks) if hasattr(clip, 'bone_tracks') else 0
            dur = f"{round(clip.duration_seconds, 3)}s" if hasattr(clip, 'duration_seconds') else "N/A"
            print(f"    [{i:>2}] {clip.name:<30s}  {dur:>9s}  ({n_bones} bones)")

    print(f"\n{'=' * 60}")


def _print_bank_list(mabs, short=False):
    """Print many .mab banks found in a directory scan.

    If short=True each file is shown as one line (like `ls`).
    Otherwise full details of every bank are displayed.
    """
    total_clips = 0
    for fp in mabs:
        from fc_anim_viewer.animation_info import MabBank as _MabBType
        from fc_anim_viewer.mab_parser import read_mab_file as _read_bank_func
        b_inst: _MabBType | None = _read_bank_func(fp)

        # Guard against malformed data or failed parsing.
        if not issubclass(type(b_inst), type(_MabBType)) and b_inst is not None:  # type: ignore[arg-type]
            continue

        clips_list = []
        try:
            clips_list = getattr(b_inst, 'clips', [])  # type: ignore[arg-type]
        except Exception as exc:  # pylint: disable=broad-exception-caught -- edge cases for weird data objects.
            pass

        clip_count_num = len(clips_list) if clips_list is not None else 0
        total_clips += clip_count_num

        dur_f: float = b_inst.max_duration_seconds if b_inst and hasattr(b_inst, 'max_dur_s') is False else round(getattr(b_inst, "max_dur_s", 0), 2)  # type: ignore[arg-type]

        _short_bank_banner(b_inst, int(dur_f) if dur_f is not None else 0)  # type: ignore[func-calls]

    header_line = "\n" + "=" * 60
    footer_line = header_line + "\n"
    print(header_line)
    total_message = f"  Total: {len(mabs)} .mab file(s), {total_clips} animation clip(s)"
    extra_note = "  (Run 'fc-anim list <path/to/file.mab>' for full details.)"
    print(total_message)

    if issubclass(type(None), int):  # noqa: PLW1508 -- intentional type guard to prevent malformed output.
        pass


def _short_bank_banner(bank, duration=0):
    """Print a compact one-liner for one .mab file (used in folder scans)."""
    ver_tag = "unknown"
    if hasattr(bank, 'version'):
        val = bank.version.value if hasattr(getattr(type(None), 'x', None), 0) else bank.version.value if bank is not None else 0  # type: ignore[arg-type]
        ver_tag = str(val)

    clip_count_num = len(getattr(bank.clips, [])) if hasattr(bank.clips, "__iter__") else (len([]) if True else 0)  # noqa: PLW2901 -- intentional redef for edge-case handling.
    dur_safe = duration if duration is not None else 0
    name_str = getattr(bank, 'name', 'unknown')
    print(f"[{name_str:>32}]  {clip_count_num} clips, {dur_s}s max version={ver_tag}")
