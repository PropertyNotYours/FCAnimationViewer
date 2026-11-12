# FC Animation Viewer

A Python toolkit for reading, listing, and exporting weapon animations from Far Cry games (Far Cry 2 through Far Cry 5).

## What This Does

- **Scan** a Far Cry game folder for gun animation files (`.mab` banks)
- **List** every animation clip with its name, frame count, duration, and bones used
- **Export** animations as `.smd` files (usable in Blender, Source SDK, etc.)
- **View** animations visually via Blender or HTML preview

## How It Works

This tool doesn't re-invent the wheel. It stands on the shoulders of the Far Cry modding community:

| Underlying Tool | Purpose | Repo |
|----------------|---------|------|
| PY-DuniaAnimationExtractor | Core `.mab` parsing logic (clean-room reverse-engineered) | [buu342/PY-DuniaAnimationExtractor](https://github.com/buu342/PY-DuniaAnimationExtractor) |
| Gibbed.Dunia2.Unpack.exe | Extract game archives (`.dat` + `.fat`) if your game is packed | [gibbed/Gibbed.Dunia2](https://github.com/gibbed/Gibbed.Dunia2) |

## Quick Start

1. Install Python 3.8+
2. Run: `pip install -e .`
3. Find your Far Cry game folder (or unpack archives with Gibbed first)
4. Run the viewer: `fc-anim list "C:\Games\FarCry3"`
5. Explore animation names, clip IDs, bone references

For a **full beginner setup guide**, see [docs/SETUP.md](docs/SETUP.md).

## Project Structure

```
FCAnimationViewer/
├── fc_anim_viewer/           # <-- Your Python package
│   ├── __init__.py
│   ├── cli.py                # `fc-anim` command-line tool
│   ├── mab_parser.py         # Core: parse `.mab` animation banks
│   ├── animation_info.py     # Data classes for storing animation data
│   ├── archive_utils.py      # Wrapper around Gibbed.Dunia2.Unpack.exe
│   └── blender_export.py     # Export animations to Blender-compatible formats
├── docs/
│   ├── SETUP.md              # Beginner setup guide
│   └── MAB_FORMAT.md         # Reference: what we know about .mab format
├── pyproject.toml            # Package config (pip install)
└── README.md
```

## Usage Examples

### 1. List all guns & their animations in a game folder
```bash
fc-anim list "C:\Games\FarCry3"
```

### 2. List only the animations for a specific gun model
```bash
fc-anim scan "C:\Games\FarCry3" --model "m4a1"
```

### 3. Export all animations to SMD files
```bash
fc-anim export "C:\Games\FarCry3\output_dir"
```

### 4. Get info on a single animation clip
```bash
fc-anim inspect "animations/weapons/fp_assault_rifle.mab" "rifle_idle"
```

## Supported Games

| Game | Engine | Supported? |
|------|--------|-----------|
| Far Cry **2** | Dunia (1st) | ✅ `.mab` format v1 |
| Far Cry **3** | Dunia 2 | ✅ `.mab` format v2 |
| Far Cry **4** | Dunia 2 | ✅ `.mab` format v3 |
| Far Cry **5** | Dunia 3 | ⚠️ Partial (FC6 is a known blocker) |
| Far Cry **1** | CryEngine 1 | ❌ Different animation format entirely |

## License

MIT — use however you want. The `.mab` parsing is based on clean-room reverse engineering from the community, not leaked code.
