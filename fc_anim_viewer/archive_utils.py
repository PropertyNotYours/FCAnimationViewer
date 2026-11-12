"""Archive extraction utility -- wrapper around Gibbed.Dunia2.Unpack.exe.

Far Cry 3+ games store assets in packed BigFile archives (.dat + .fat).
This module helps you locate and invoke the tool to extract them.

Usage
-----
    from fc_anim_viewer.archive_utils import GIBBED_PATH, unpack_game_folder

    # Find the Gibbed tool on your system
    print(GIBBED_PATH)             # Auto-detected path or None

    # Extract game archives to a flat folder
    result = unpack_game_folder(
        game_path="C:/Games/FarCry3",
        output_dir="C:/Games/FC3_Extracted"
    )
    if not result.success:
        print(f"Error: {result.stderr}")

    # Or tell the tool where Gibbed lives manually:
    from fc_anim_viewer.archive_utils import set_gibbed_path
    set_gibbed_path("c:/tools/Gibbed.Dunia2.Unpack.exe")
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


# Common locations for Gibbed.Dunia2.Unpack.exe
_GIBBED_PATHS: list[Path] = [
    Path.home() / "Downloads" / "Gibbed.Dunia2" / "Gibbed.Dunia2.Unpack.exe",
    Path.home() / "Documents" / "DuniaTools" / "Gibbed.Dunia2.Unpack.exe",
    Path("C:/Games/DuniaTools/Gibbed.Dunia2.Unpack.exe"),
]

_GIBBED_PATH: Path | None = _auto_detect_gibbed()


def _auto_detect_gibbed():
    """Search common locations for Gibbed.Dunia2.Unpack.exe and return its path."""
    p: Path
    for p in list(_GIBBED_PATHS):
        if p.exists():
            return p

    # Also check PATH via the Windows `where` command.
    try:
        result = subprocess.run(
            ["where", "Gibbed.Dunia2.Unpack.exe"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            candidates = [Path(p) for p in result.stdout.splitlines()]
            for c in candidates:
                if c.exists():
                    return c
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Try the environment variable FC_ANIM_GIBBED first.
    env = os.environ.get("FC_ANIM_GIBBED")
    if env and Path(env).exists():
        return Path(env)

    return None


def set_gibbed_path(path_arg: str | Path):
    """Override auto-detected path with a specific Gibbed.Unpack executable."""
    global GIBBED_PATH  # noqa: PLW0603 -- intentional module-level override
    GIBBED_PATH = Path(path_arg)


@dataclass(slots=True)
class ArchiveOperationResult:
    """Result of running Gibbed.Dunia2.Unpack on a game folder."""
    success: bool
    output_dir: Path | None = None
    stderr: str = ""


def unpack_game_folder(
    game_path: str | Path,
    output_dir: str | Path | None = None,
) -> ArchiveOperationResult:
    """Unpack Far Cry game archives using Gibbed.Dunia2.Unpack.exe.

    This is the FIRST step for any Far Cry 3+ installation that uses
    BigFile archive packing (.dat + .fat). You must unpack before you
    can browse the .mab animation banks inside.

    Args:
        game_path: Path to the installed Far Cry game folder
                   (parent of /bin/, /Data/, etc.).
        output_dir: Where to put extracted files. Defaults to
                    <game_path>_extracted.

    Returns:
        ArchiveOperationResult with success flag and error message if failed.
    """
    if GIBBED_PATH is None or not GIBBED_PATH.exists():
        return ArchiveOperationResult(
            success=False,
            output_dir=None,
            stderr=_NO_GIBBED_MESSAGE,
        )

    game = Path(game_path)
    if not output_dir:
        output_dir = game.parent / f"{game.name}_extracted"
    else:
        output_dir = Path(output_dir)

    cmd = [str(GIBBED_PATH), str(game.resolve())]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes max for large games.
        )
        if result.returncode != 0:
            return ArchiveOperationResult(success=False, output_dir=None, stderr=result.stderr)
        return ArchiveOperationResult(success=True, output_dir=output_dir)

    except subprocess.TimeoutExpired:
        return ArchiveOperationResult(False, None, "Unpack timed out after 10 minutes.")
    except OSError as exc:
        return ArchiveOperationResult(False, None, f"Could not execute Gibbed tool: {exc}")


# ------------------------------------------------------------------
# Messages displayed when the user has no Gibbed tool installed yet.
# -------------------------------------------------------------------

_NO_GIBBED_MESSAGE = (
    "Gibbed.Dunia2.Unpack.exe not found.\n"
    "\n"
    "Download from:\n"
    "  https://github.com/gibbed/Gibbed.Dunia2/releases\n"
    "\n"
    "Then place Gibbed.Dunia2.Unpack.exe somewhere and run:\n"
    "  fc-anim set-gibbed <path/to/Gibbed.Dunia2.Unpack.exe>\n"
)
