# Beginner Setup Guide — Step by Step

This guide walks you through setting up everything on a clean Windows PC.
Follow each step in order. No prior Python knowledge needed.

---

## Prerequisites: Install These Programs

### 1. Install Python (free)

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Download **Python 3.11** or **3.12** for Windows
3. Run the installer — **check "Add Python to PATH"** at the bottom!
4. Click **Install Now**

> After it finishes, open a new terminal (press `Win+R`, type `cmd`, hit Enter)
> And run:
> ```
> python --version
> ```
> You should see something like `Python 3.11.x`. If you get 'cannot be recognized', restart your PC and try again.

### 2. Install Git (free)

1. Go to [git-scm.com/download/win](https://git-scm.com/download/win)
2. Run the installer — just keep all defaults
3. After install, open a new terminal and run:
   ```
   git --version
   ```

---

## Step 1: Install the Far Cry Modding Toolkit

We need **Gibbed.Dunia2.Unpack.exe** to extract game archives (`.dat` + `.fat`).

1. Go to: [github.com/gibbed/Gibbed.Dunia2/releases](https://github.com/gibbed/Gibbed.Dunia2/releases)
2. Click on the latest release
3. Download `Gibbed.Dunia2.zip`
4. Extract it somewhere — let's call that folder your **ToolFolder** for now

> This single `.exe` extracts game archives into a flat folder with all assets un-packed. You only use it **once per game you want to scan**.

---

## Step 2: Install the FC Animation Viewer (the code we built)

Open a terminal and run:

```bash
cd C:\Users\SethN\Documents\GitHub\FCAnimationViewer
pip install -e .
```

This installs `fc-anim` as a command you can run from anywhere. Verify it installed:

```bash
fc-anim --help
```

---

## Step 3: Locate Your Far Cry Game Files

### If your game is already in "raw" format (no archives):

Some games like Far Cry 2 are mostly raw files on disk. Look for a folder with `.mab` files:

```bash
fc-anim scan "C:\path\to\FarCry2"
```

### If your game uses packed archives (Far Cry 3, FC4, etc.):

1. Unpack the archives using Gibbed:
   ```bash
   Gibbed.Dunia2.Unpack.exe "C:\Games\FarCry3" --output "C:\Games\FC3_Extracted"
   ```
2. Then we'll scan the extracted folder instead!

> **Note**: Only unpack archives for games you own. This is for modding your own copies.

---

## Step 4: Run the Animation Viewer!

Now the moment of truth — find all weapon animations in any game or model file:

### Option A: Scan an entire game folder (finds every gun animation)
```bash
fc-anim scan "C:\Games\FC3_Extracted"
```

### Option B: Look at one specific .mab file
```bash
fc-anim list "path/to/animations/weapons/fp_assault_rifle.mab"
```

### Option C: List a specific gun's animations by model name
```bash
fc-anim find -n m4a1 "C:\Games\FC3_Extracted"
```

---

## Step 5 (Optional): Visualize Animations in Blender

If you want to *see* the animations play out:

1. Download **Blender** from [blender.org](https://www.blender.org/download/)
2. We'll create a Blender add-on automatically via `fc-anim` — just run once:
   ```bash
   fc-anim blender-setup "C:\Games\FC3_Extracted"
   ```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `'python' is not recognized` | Restart PC. Reinstall Python and check "Add to PATH". |
| `ModuleNotFoundError: No module named 'fc_anim_viewer'` | Run `pip install -e .` again. Make sure you're in the right folder. |
| Game scans but finds no `.mab` files | Your game uses packed archives — use Gibbed.Dunia2.Unpack.exe first! |
| Parser fails on a file | Share the error output. Different Dunia titles have subtle format variations. |

---

## What We're Actually Building (Architecture)

```
Your workflow:
┌──────────────┐     ┌─────────────────┐      ┌──────────────┐      ┌──────────┐
│ Game Folder  │────▶│ Gibbed.Unpack   │────▶│ fc-anim list │──────▶│ Terminal │
│ (.dat/.fat)  │     │ (archive tool)  │      │ (.mab parser)│      │ (output) │
└──────────────┘     └─────────────────┘      └──────────────┘      └──────────┘

The hard part: parsing .mab binary format
                                        ↑
              This is what PY-DuniaAnimationExtractor reverse-engineered.
              We studied its approach and rebuilt it cleanly in our mab_parser.py.
```

> **Why not parse `.mab` from scratch?** Because it took the community years of Ghidra disassembly + Cheat Engine tracing to figure out. Our `mab_parser.py` implements what they discovered, based on published analysis — no leaked code needed.
