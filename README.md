# ORIC Hires Picture Editor

A visual pixel editor for the [Tangerine ORIC](https://en.wikipedia.org/wiki/Oric) hires mode (240×200, 8 colours). Paint freely, then compile to apply ORIC hardware constraints via PictConv.

![ORIC Hires](https://img.shields.io/badge/ORIC-Hires%20240x200-blue)
![Python](https://img.shields.io/badge/Python-3.8%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

- **Free Paint** — 8 ORIC colours, adjustable brush (1–20px)
- **Eyedropper** — right-click to pick colour
- **Shift+click** — replace row background colour
- **ImageBG** — replace most common colour across entire image
- **Import** — load PNG/JPG/BMP/GIF, auto-resize to 240×200, convert via PictConv
- **Compile** — export canvas to PNG → PictConv → reload optimised result
- **Run in Emulator** — build a `.tap` and launch in Oricutron
- **Open / Save / SaveAs** — read and write `.s` assembly files (`_LabelPicture` format)
- **Zoom** — 1×–10× (Ctrl+mousewheel or toolbar buttons)
- **Grid overlay** — 6-pixel attribute cell boundaries
- **Setup dialog** — set OSDK root to auto-fill all tool paths; optional auto-copy of emulator build files

## Prerequisites

- **Python 3.8+** with **tkinter** (usually bundled with Python)
- **[Pillow](https://pypi.org/project/Pillow/)** — `pip install Pillow` (required for Import and Compile)
- **[OSDK 1.21](http://osdk.defence-force.org/)** — provides PictConv, Oricutron, and make.bat (required for Compile, Import, and Run in Emulator)
- **[PyInstaller](https://pypi.org/project/pyinstaller/)** — `pip install pyinstaller` (only needed to build the standalone exe)

| Mode | What you need | What works |
|------|--------------|------------|
| **Standalone** | Python 3.8+ with tkinter | New, Open, Save, Paint, Zoom, Grid |
| **With OSDK** | + Pillow, OSDK toolchain | + Import, Compile, Run in Emulator |

## Quick Start

### Run from source

```bash
pip install Pillow
python src/picture_editor.py                    # blank canvas
python src/picture_editor.py samples/picture_sample.s  # edit existing
python src/picture_editor.py myimage.png        # import image
```

### Run the prebuilt exe

The release build is at `build/release/OricHiresPictureEditor.exe`. On first run, click **Setup** to set the OSDK root path — this auto-fills PictConv, Oricutron, and make.bat locations.

Tick **Auto-copy emulator files** to have `osdk_config.bat` and `main.c` copied from the OSDK hires_picture sample into the `temp/` folder automatically.

## Configuration

Paths are stored in `config.json` next to the exe (or script). Use the **Setup** button in the toolbar to configure:

| Field | Purpose |
|-------|---------|
| OSDK root | Auto-fills the three paths below |
| PictConv.exe | Image → ORIC converter (Compile, Import) |
| Oricutron.exe | ORIC emulator (Run) |
| make.bat | OSDK build script (Run) |
| Temp folder | Working directory for builds (defaults to `temp/` next to app) |
| Auto-copy | Copies `osdk_config.bat` and `main.c` from OSDK sample to temp |

## Building the Executable

```bash
pip install pyinstaller pillow
python src/build_exe.py             # Release build (windowed, no console)
python src/build_exe.py --dev       # Dev build (with console for debugging)
```

Output:
```
build/release/                      # or build/dev/
  OricHiresPictureEditor.exe
  config.json
  temp/
```

## Project Structure

```
src/
  picture_editor.py     # Main editor (standalone + OSDK integration)
  build_exe.py          # PyInstaller build script
build/
  release/              # Release exe + config + temp/
config.json             # Source config template (empty defaults)
samples/                # Sample .s files and images
```

## Shortcuts

| Input | Action |
|-------|--------|
| Left-click / drag | Paint with selected colour |
| Right-click | Eyedropper (pick colour) |
| Shift+click / drag | Replace row background colour |
| Ctrl+mousewheel | Zoom in/out |

## Acknowledgements

This project relies on the **OSDK** (Oric Software Development Kit) by **Dbug (Defence Force)**:

- **[OSDK](http://osdk.defence-force.org/)** — the toolchain for ORIC development
- **PictConv** — image conversion tool; its `-f6` mode implements the **Img2Oric** algorithm for optimal ORIC hires colour conversion
- **Oricutron** — ORIC emulator included with the OSDK distribution

Thanks to Dbug and the Defence Force team for maintaining these tools and keeping ORIC development alive.

## License

MIT License. See [LICENSE](LICENSE) for details.
