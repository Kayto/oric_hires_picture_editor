#!/usr/bin/env python3
"""
ORIC Hires Picture Editor

A visual pixel editor for the Tangerine ORIC 8-bit computer's hires
graphics mode (240x200, 8 colours).

Standalone: Create, edit, and save .s picture data files with no
external dependencies beyond Python + tkinter.

OSDK integration (optional): Import images, Compile (PictConv), and
Run in Oricutron require the OSDK toolchain. A setup wizard prompts
for paths on first use of these features.

Author:  kayto
Version: 1.0 (2024-06)
License: MIT

Usage:
  python picture_editor.py              # Start with new blank canvas
  python picture_editor.py image.s      # Edit existing .s file
  python picture_editor.py image.png    # Import and convert image

Requires: Python 3.8+, tkinter (usually bundled with Python)
Optional: Pillow (for Import), OSDK (for PictConv / Oricutron)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, filedialog

WIDTH = 240
HEIGHT = 200

ORIC_COLORS = {
    0: "#000000",  1: "#FF0000",  2: "#00FF00",  3: "#FFFF00",
    4: "#0000FF",  5: "#FF00FF",  6: "#00FFFF",  7: "#FFFFFF",
}
ORIC_NAMES = ["Black", "Red", "Green", "Yellow", "Blue", "Magenta", "Cyan", "White"]
ORIC_RGB = {
    0: (0, 0, 0), 1: (255, 0, 0), 2: (0, 255, 0), 3: (255, 255, 0),
    4: (0, 0, 255), 5: (255, 0, 255), 6: (0, 255, 255), 7: (255, 255, 255),
}


def _get_app_dir():
    """Get the application directory (handles both script and frozen exe)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _get_config_path():
    """Get path to config.json next to the app."""
    app_dir = _get_app_dir()
    for p in [os.path.join(app_dir, 'config.json'),
              os.path.join(app_dir, '..', 'config.json')]:
        if os.path.exists(p):
            return os.path.normpath(p)
    return os.path.join(app_dir, 'config.json')


def load_config():
    """Load configuration from config.json."""
    config = {
        'pictconv_path': '',
        'oricutron_path': '',
        'make_bat_path': '',
        'temp_dir': '',
        'default_save_dir': '',
        'auto_copy_emu_files': False,
    }
    config_path = _get_config_path()
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                loaded = json.load(f)
                for key in config:
                    if key in loaded and loaded[key] is not None:
                        config[key] = loaded[key]
        except (json.JSONDecodeError, IOError):
            pass
    return config


def save_config(config):
    """Save configuration to config.json."""
    config_path = _get_config_path()
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        print(f"Warning: Could not save config: {e}")


def _derive_osdk_root(config):
    """Derive OSDK root from configured tool paths, or empty string."""
    for key in ('pictconv_path', 'make_bat_path'):
        p = config.get(key, '')
        if p and 'bin' in p.replace('\\', '/').lower():
            candidate = os.path.dirname(os.path.dirname(p))
            if os.path.isdir(candidate):
                return candidate
    return ''


def _copy_emu_sample_files(osdk_root, temp_dir, overwrite=False):
    """Copy osdk_config.bat and main.c from OSDK hires_picture sample to temp."""
    sample_dir = os.path.join(osdk_root, 'sample', 'c', 'hires_picture')
    copied = []
    for fname in ['osdk_config.bat', 'main.c']:
        src = os.path.join(sample_dir, fname)
        dst = os.path.join(temp_dir, fname)
        if os.path.isfile(src) and (overwrite or not os.path.isfile(dst)):
            os.makedirs(temp_dir, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(fname)
    return copied


def _show_setup(config):
    """Dialog to set OSDK root (auto-fills tool paths) and temp directory.

    Returns True if paths were saved, False if cancelled.
    """
    dlg = tk.Toplevel()
    dlg.title("Path Setup")
    dlg.geometry("540x340")
    dlg.resizable(False, False)
    dlg.grab_set()

    result = {'ok': False}

    tk.Label(dlg, text="Set paths for Compile and Run",
             font=("Arial", 11, "bold")).pack(pady=(10, 6))

    def _browse_file(var, title, ftypes):
        p = filedialog.askopenfilename(title=title, filetypes=ftypes)
        if p:
            var.set(p)

    def _browse_dir(var, title):
        p = filedialog.askdirectory(title=title)
        if p:
            var.set(p)

    def _row(parent, label, var, browse_cmd):
        frm = tk.Frame(parent)
        frm.pack(fill=tk.X, padx=15, pady=3)
        tk.Label(frm, text=label, width=14, anchor=tk.W).pack(side=tk.LEFT)
        tk.Entry(frm, textvariable=var, width=42).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(frm, text="Browse", command=browse_cmd).pack(side=tk.LEFT, padx=4)

    exe_ft = [("Executable", "*.exe"), ("All", "*.*")]
    bat_ft = [("Batch file", "*.bat"), ("All", "*.*")]

    # --- OSDK root (auto-fills the paths below) ---
    pic_var = tk.StringVar(value=config.get('pictconv_path', ''))
    emu_var = tk.StringVar(value=config.get('oricutron_path', ''))
    make_var = tk.StringVar(value=config.get('make_bat_path', ''))

    def _on_osdk_set(*_):
        root = osdk_var.get().strip()
        if root and os.path.isdir(root):
            pic = os.path.join(root, 'bin', 'PictConv.exe')
            mak = os.path.join(root, 'bin', 'make.bat')
            emu = os.path.join(root, 'Oricutron', 'oricutron.exe')
            if os.path.isfile(pic):
                pic_var.set(pic)
            if os.path.isfile(mak):
                make_var.set(mak)
            if os.path.isfile(emu):
                emu_var.set(emu)

    osdk_var = tk.StringVar(value=_derive_osdk_root(config))
    _row(dlg, "OSDK root:", osdk_var,
         lambda: _browse_dir(osdk_var, "Select OSDK root folder"))
    osdk_var.trace_add('write', _on_osdk_set)

    tk.Frame(dlg, height=1, bg="#ccc").pack(fill=tk.X, padx=15, pady=4)

    _row(dlg, "PictConv.exe:", pic_var,
         lambda: _browse_file(pic_var, "Select PictConv.exe", exe_ft))

    _row(dlg, "Oricutron.exe:", emu_var,
         lambda: _browse_file(emu_var, "Select Oricutron.exe", exe_ft))

    _row(dlg, "make.bat:", make_var,
         lambda: _browse_file(make_var, "Select OSDK make.bat", bat_ft))

    default_temp = os.path.join(_get_app_dir(), 'temp')
    temp_var = tk.StringVar(value=config.get('temp_dir', default_temp))
    _row(dlg, "Temp folder:", temp_var,
         lambda: _browse_dir(temp_var, "Select temp folder"))

    # --- Auto-copy emulator files checkbox ---
    auto_copy_var = tk.BooleanVar(value=config.get('auto_copy_emu_files', False))
    chk_frm = tk.Frame(dlg)
    chk_frm.pack(fill=tk.X, padx=15, pady=(6, 0))
    tk.Checkbutton(chk_frm, text="Auto-copy osdk_config.bat & main.c to temp folder",
                   variable=auto_copy_var).pack(anchor=tk.W)
    tk.Label(chk_frm, text="(from OSDK hires_picture sample when OSDK root is set)",
             font=("Arial", 8), fg="#666").pack(anchor=tk.W, padx=20)

    # --- Buttons ---
    def on_save():
        config['pictconv_path'] = pic_var.get().strip()
        config['oricutron_path'] = emu_var.get().strip()
        config['make_bat_path'] = make_var.get().strip()
        config['temp_dir'] = temp_var.get().strip()
        config['auto_copy_emu_files'] = auto_copy_var.get()
        save_config(config)

        # Auto-copy emulator build files if checkbox is ticked
        if auto_copy_var.get():
            osdk_root = osdk_var.get().strip()
            temp = temp_var.get().strip() or os.path.join(_get_app_dir(), 'temp')
            if osdk_root and os.path.isdir(osdk_root):
                copied = _copy_emu_sample_files(osdk_root, temp, overwrite=True)
                if copied:
                    messagebox.showinfo("Files Copied",
                                        f"Copied to temp folder:\n  {', '.join(copied)}")

        result['ok'] = True
        dlg.destroy()

    btn_frame = tk.Frame(dlg)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Save", command=on_save, width=10).pack(side=tk.LEFT, padx=8)
    tk.Button(btn_frame, text="Cancel", command=dlg.destroy, width=8).pack(side=tk.LEFT, padx=8)

    dlg.wait_window()
    return result['ok']


# Global config loaded once at startup
CONFIG = load_config()


class OricPictureEditor:
    def __init__(self, filename=None):
        self.filename = filename or 'untitled.s'
        self.zoom = 3
        self.paint_color = 0
        self.show_grid = False
        self._init_arrays()
        
        # Check if we're loading an existing file, importing an image, or starting blank
        if filename:
            ext = os.path.splitext(filename)[1].lower()
            if ext in ('.png', '.jpg', '.jpeg', '.bmp', '.gif'):
                # Import external image
                self._create_blank()
                self.create_gui()
                self._import_image_file(filename)
                return
            elif os.path.exists(filename):
                self.load_picture()
            else:
                # File doesn't exist yet, start with blank
                self._create_blank()
        else:
            self._create_blank()
        self.create_gui()

    def _init_arrays(self):
        self.pixels = [[0] * WIDTH for _ in range(HEIGHT)]
        self.colors = [[0] * WIDTH for _ in range(HEIGHT)]
        self.ink_map = [[7] * WIDTH for _ in range(HEIGHT)]
        self.paper_map = [[0] * WIDTH for _ in range(HEIGHT)]
        self.ink_byte_idx = [[-1] * WIDTH for _ in range(HEIGHT)]
        self.paper_byte_idx = [[-1] * WIDTH for _ in range(HEIGHT)]
        self.is_attr_cell = [[False] * WIDTH for _ in range(HEIGHT)]
        self.cell_inv = [[False] * WIDTH for _ in range(HEIGHT)]
        self.raw_data = []
        self.dirty_rows = set()

    def _create_blank(self):
        """Initialize a blank canvas with black background and white ink."""
        # Each row: $10 (paper black), $07 (ink white), then 38 empty pixel bytes ($40)
        for row in range(HEIGHT):
            row_bytes = [0x10, 0x07] + [0x40] * 38
            self.raw_data.append(row_bytes)
            for col in range(WIDTH):
                self.pixels[row][col] = 0
                self.colors[row][col] = 0
                self.ink_map[row][col] = 7
                self.paper_map[row][col] = 0
                self.ink_byte_idx[row][col] = 1
                self.paper_byte_idx[row][col] = 0
                self.is_attr_cell[row][col] = col < 12  # First two bytes are attributes
                self.cell_inv[row][col] = False
        print(f"Created blank {WIDTH}x{HEIGHT} canvas")

    # -------------------------------------------------------------- Load
    def load_picture(self):
        with open(self.filename, 'r') as f:
            content = f.read()

        all_bytes = []
        for line in content.split('\n'):
            if '.byt' in line:
                match = re.search(r'\.byt\s+(.*)', line)
                if match:
                    for b in match.group(1).split(','):
                        b = b.strip()
                        if b.startswith('$'):
                            all_bytes.append(int(b[1:], 16))

        print(f"Total bytes: {len(all_bytes)}")

        for row in range(HEIGHT):
            row_start = row * 40
            if row_start + 40 > len(all_bytes):
                break

            row_bytes = all_bytes[row_start:row_start + 40]
            self.raw_data.append(row_bytes[:])

            col, ink, paper = 0, 7, 0
            last_ink_byte, last_paper_byte = -1, -1

            for byte_idx, v in enumerate(row_bytes):
                if (v & 0x60) == 0x00:  # Attribute byte
                    attr_type = v & 0x18
                    if attr_type == 0x00:
                        ink = v & 0x07
                        last_ink_byte = byte_idx
                    elif attr_type == 0x10:
                        paper = v & 0x07
                        last_paper_byte = byte_idx

                    inv = (v & 0x80) != 0
                    fg = (ink ^ 7) if inv else ink
                    bg = (paper ^ 7) if inv else paper
                    for _ in range(6):
                        if col < WIDTH:
                            self.pixels[row][col] = 0
                            self.colors[row][col] = bg
                            self.ink_map[row][col] = fg
                            self.paper_map[row][col] = bg
                            self.ink_byte_idx[row][col] = last_ink_byte
                            self.paper_byte_idx[row][col] = last_paper_byte
                            self.is_attr_cell[row][col] = True
                            self.cell_inv[row][col] = inv
                            col += 1
                else:  # Pixel byte
                    inv = (v & 0x80) != 0
                    data = v & 0x3F
                    fg = (ink ^ 7) if inv else ink
                    bg = (paper ^ 7) if inv else paper
                    for bit in range(5, -1, -1):
                        if col < WIDTH:
                            pixel_on = (data >> bit) & 1
                            self.pixels[row][col] = pixel_on
                            self.colors[row][col] = fg if pixel_on else bg
                            self.ink_map[row][col] = fg
                            self.paper_map[row][col] = bg
                            self.ink_byte_idx[row][col] = last_ink_byte
                            self.paper_byte_idx[row][col] = last_paper_byte
                            self.is_attr_cell[row][col] = False
                            self.cell_inv[row][col] = inv
                            col += 1

        print(f"Loaded {HEIGHT} rows")

    # -------------------------------------------------------------- GUI
    def create_gui(self):
        self.root = tk.Tk()
        self.root.title("ORIC Hires Picture Editor - " + self.filename)

        # ---- Toolbar ----
        tb = tk.Frame(self.root, bd=1, relief=tk.RAISED)
        tb.pack(side=tk.TOP, fill=tk.X)

        tk.Button(tb, text="New", command=self.new_picture, width=4).pack(side=tk.LEFT, padx=1)
        tk.Button(tb, text="Open", command=self.load_file, width=4).pack(side=tk.LEFT, padx=1)
        tk.Button(tb, text="Import", command=self.import_image, width=5, bg="#E0E0FF").pack(side=tk.LEFT, padx=1)
        tk.Button(tb, text="Save", command=self.save_picture, width=4).pack(side=tk.LEFT, padx=1)
        tk.Button(tb, text="SaveAs", command=self.save_as, width=5).pack(side=tk.LEFT, padx=1)

        self._sep(tb)

        tk.Button(tb, text="\u2212", command=self.zoom_out, width=2).pack(side=tk.LEFT)
        self.zoom_lbl = tk.Label(tb, text=f"{self.zoom}x", width=2)
        self.zoom_lbl.pack(side=tk.LEFT)
        tk.Button(tb, text="+", command=self.zoom_in, width=2).pack(side=tk.LEFT)

        self._sep(tb)

        tk.Label(tb, text="Brush:").pack(side=tk.LEFT)
        self.brush_size = tk.IntVar(value=1)
        tk.Spinbox(tb, from_=1, to=20, width=2, textvariable=self.brush_size).pack(side=tk.LEFT)

        self._sep(tb)

        self.grid_btn = tk.Button(tb, text="Grid", command=self.toggle_grid, width=4)
        self.grid_btn.pack(side=tk.LEFT, padx=1)
        tk.Button(tb, text="ImageBG", command=self.set_image_paper, width=6).pack(side=tk.LEFT, padx=1)

        self._sep(tb)

        tk.Button(tb, text="Compile", command=self.compile_picture,
                  width=6, bg="#FFD700").pack(side=tk.LEFT, padx=1)
        tk.Button(tb, text="Run", command=self.run_in_emulator,
                  width=4, bg="#90EE90").pack(side=tk.LEFT, padx=1)
        tk.Button(tb, text="Setup", command=self.setup_paths,
                  width=5).pack(side=tk.LEFT, padx=1)

        self.coord_lbl = tk.Label(tb, text="X:--- Y:---", width=28, anchor=tk.E,
                                  font=("Consolas", 9))
        self.coord_lbl.pack(side=tk.RIGHT, padx=4)

        # ---- Palette ----
        pal_frame = tk.Frame(self.root, bd=1, relief=tk.RAISED)
        pal_frame.pack(side=tk.TOP, fill=tk.X)

        tk.Label(pal_frame, text="Palette:").pack(side=tk.LEFT, padx=4)

        self.pal_btns = {}
        for i in range(8):
            c = ORIC_COLORS[i]
            fg = "#FFFFFF" if i in (0, 4) else "#000000"
            btn = tk.Button(pal_frame, text=ORIC_NAMES[i], bg=c, fg=fg,
                            activebackground=c, width=6, bd=2, relief=tk.RAISED,
                            command=lambda idx=i: self.select_color(idx))
            btn.pack(side=tk.LEFT, padx=1)
            self.pal_btns[i] = btn

        self._sep(pal_frame)
        self.mode_lbl = tk.Label(pal_frame, text="", font=("Arial", 9))
        self.mode_lbl.pack(side=tk.LEFT, padx=4)

        self.select_color(0)

        # ---- Canvas ----
        frame = tk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True)

        cw = min(WIDTH * self.zoom, 900)
        ch = min(HEIGHT * self.zoom, 650)
        self.canvas = tk.Canvas(frame, width=cw, height=ch, bg="#333",
                                scrollregion=(0, 0, WIDTH * self.zoom, HEIGHT * self.zoom))

        hbar = tk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        vbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self.paint)
        self.canvas.bind("<B1-Motion>", self.paint)
        self.canvas.bind("<Shift-Button-1>", self.on_shift_click)
        self.canvas.bind("<Shift-B1-Motion>", self.on_shift_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)

        self.draw_all()

    @staticmethod
    def _sep(parent):
        tk.Frame(parent, width=2, bd=1, relief=tk.SUNKEN).pack(
            side=tk.LEFT, fill=tk.Y, padx=6, pady=2)

    # ---------------------------------------------------------- Palette / Zoom
    def select_color(self, idx):
        self.paint_color = idx
        for i, btn in self.pal_btns.items():
            btn.config(relief=tk.SUNKEN if i == idx else tk.RAISED,
                       bd=3 if i == idx else 2)
        self.mode_lbl.config(text=f"{ORIC_NAMES[idx]}  |  Shift=rowBG  R-click=pick")

    def toggle_grid(self):
        self.show_grid = not self.show_grid
        self.grid_btn.config(relief=tk.SUNKEN if self.show_grid else tk.RAISED)
        self.draw_all()

    def set_image_paper(self):
        """Fill image background with selected color (replaces most common color in image)."""
        # Find most common color in entire image
        color_counts = {}
        for row in range(HEIGHT):
            for col in range(WIDTH):
                c = self.colors[row][col]
                color_counts[c] = color_counts.get(c, 0) + 1
        old_bg = max(color_counts, key=color_counts.get)
        
        # Replace all pixels of that color with new color
        new_color = self.paint_color
        for row in range(HEIGHT):
            for col in range(WIDTH):
                if self.colors[row][col] == old_bg:
                    self.colors[row][col] = new_color
            self.dirty_rows.add(row)
        self.draw_all()

    def zoom_in(self):
        if self.zoom < 10:
            self.zoom += 1
            self._apply_zoom()

    def zoom_out(self):
        if self.zoom > 1:
            self.zoom -= 1
            self._apply_zoom()

    def _apply_zoom(self):
        self.zoom_lbl.config(text=f"{self.zoom}x")
        self.canvas.config(scrollregion=(0, 0, WIDTH * self.zoom, HEIGHT * self.zoom))
        self.draw_all()

    def on_mousewheel(self, event):
        if event.state & 0x4:
            (self.zoom_in if event.delta > 0 else self.zoom_out)()
        else:
            self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    # ---------------------------------------------------------- Drawing
    def draw_all(self):
        self.canvas.delete("all")
        z = self.zoom
        w, h = WIDTH * z, HEIGHT * z
        self.img = tk.PhotoImage(width=w, height=h)
        for y in range(HEIGHT):
            self._put_row(y)
        self._canvas_img = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.img)

        if self.show_grid:
            self._draw_grid()

    def _draw_grid(self):
        """Draw attribute cell boundaries as a simple grey grid.

        - Vertical grey lines every 6 pixels (attribute cell width)
        - Horizontal grey lines every row (each row is independent)
        """
        z = self.zoom
        CELL_WIDTH = 6  # Each byte = 6 pixels

        # Vertical grey lines every 6 pixels
        for x in range(0, WIDTH + 1, CELL_WIDTH):
            self.canvas.create_line(x * z, 0, x * z, HEIGHT * z,
                                    fill="#666", width=1)

        # Horizontal grey lines every row
        for y in range(0, HEIGHT + 1):
            self.canvas.create_line(0, y * z, WIDTH * z, y * z,
                                    fill="#444", width=1, dash=(1, 3))

    def _put_row(self, y):
        z = self.zoom
        row_colors = []
        for x in range(WIDTH):
            c = ORIC_COLORS.get(self.colors[y][x], "#808080")
            row_colors.extend([c] * z)
        row_data = "{" + " ".join(row_colors) + "}"
        for zy in range(z):
            self.img.put(row_data, to=(0, y * z + zy))

    def draw_pixel(self, px, py):
        z = self.zoom
        c = ORIC_COLORS.get(self.colors[py][px], "#808080")
        row_data = "{" + " ".join([c] * z) + "}"
        x1, y1 = px * z, py * z
        for zy in range(z):
            self.img.put(row_data, to=(x1, y1 + zy))

    def _event_to_pixel(self, event):
        """Convert a canvas event to pixel coordinates, or (-1, -1) if out of bounds."""
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        x, y = int(cx // self.zoom), int(cy // self.zoom)
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            return x, y
        return -1, -1

    def on_motion(self, event):
        x, y = self._event_to_pixel(event)
        if x >= 0:
            cn = ORIC_NAMES[self.colors[y][x]]
            self.coord_lbl.config(text=f"X:{x:3d} Y:{y:3d}  Color: {cn}")
        else:
            self.coord_lbl.config(text="X:--- Y:---")

    # ---------------------------------------------------------- Input
    def on_right_click(self, event):
        """Eyedropper: pick the color under the cursor."""
        x, y = self._event_to_pixel(event)
        if x >= 0:
            self.select_color(self.colors[y][x])

    def on_shift_click(self, event):
        """Shift+click: replace most common color in row with selected color (row background)."""
        x, y = self._event_to_pixel(event)
        if x < 0:
            return
        # Find most common color in the row
        color_counts = {}
        for col in range(WIDTH):
            c = self.colors[y][col]
            color_counts[c] = color_counts.get(c, 0) + 1
        old_bg = max(color_counts, key=color_counts.get)
        
        # Replace all pixels of that color
        new_color = self.paint_color
        for col in range(WIDTH):
            if self.colors[y][col] == old_bg:
                self.colors[y][col] = new_color
        
        self.dirty_rows.add(y)
        self._put_row(y)

    # ---------------------------------------------------------- Paint
    def paint(self, event):
        """Paint pixels with selected color (pure visual - ORIC conversion happens at compile)."""
        x, y = self._event_to_pixel(event)
        if x < 0:
            return
        brush = self.brush_size.get()
        want = self.paint_color

        for dy in range(-brush + 1, brush):
            for dx in range(-brush + 1, brush):
                px, py = x + dx, y + dy
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    if self.colors[py][px] != want:
                        self.colors[py][px] = want
                        self.dirty_rows.add(py)
                        self.draw_pixel(px, py)

    # -------------------------------------------------------- OSDK Integration
    def _find_tool(self, config_key):
        """Return tool path from config, or None."""
        p = CONFIG.get(config_key, '')
        return p if p and os.path.isfile(p) else None

    def _require_tool(self, config_key, display_name):
        """Return tool path, or prompt user to set it up."""
        p = self._find_tool(config_key)
        if p:
            return p
        if messagebox.askyesno(f"{display_name} not configured",
                               f"{display_name} path is not set.\n\nOpen path setup?"):
            if _show_setup(CONFIG):
                return self._find_tool(config_key)
        return None

    def setup_paths(self):
        """Open the path setup dialog."""
        _show_setup(CONFIG)

    def _ensure_saved(self):
        """Prompt user to save if file is untitled or missing. Returns True if saved."""
        if self.filename == 'untitled.s' or not os.path.exists(self.filename):
            if messagebox.askyesno("Save First",
                                   "Please save the file first.\n\nSave now?"):
                self.save_as()
                return self.filename != 'untitled.s'
            return False
        return True

    def _get_temp_dir(self):
        """Get the temp directory from config, or default to temp/ next to the app."""
        temp_dir = CONFIG.get('temp_dir', '').strip()
        if not temp_dir:
            temp_dir = os.path.join(_get_app_dir(), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        return temp_dir

    def _require_pillow(self):
        """Return PIL.Image module, or show error and return None."""
        try:
            from PIL import Image
            return Image
        except ImportError:
            messagebox.showerror("Error", "Pillow (PIL) is required.\n"
                                 "Install with: pip install Pillow")
            return None

    def _run_pictconv(self, input_png, output_s):
        """Run PictConv on input_png -> output_s.  Returns True on success."""
        pictconv = self._require_tool('pictconv_path', 'PictConv.exe')
        if not pictconv:
            return False
        try:
            orig_mtime = os.path.getmtime(output_s) if os.path.exists(output_s) else 0
            cmd = [pictconv, '-f6', '-d0', '-o4_LabelPicture', input_png, output_s]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            new_mtime = os.path.getmtime(output_s) if os.path.exists(output_s) else 0
            if new_mtime <= orig_mtime:
                messagebox.showerror("PictConv Error",
                                     f"PictConv failed:\n{result.stderr}\n{result.stdout}")
                return False
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run PictConv:\n{e}")
            return False

    def _update_title(self):
        """Update the window title bar with current filename."""
        self.root.title("ORIC Hires Picture Editor - " + self.filename)

    def run_in_emulator(self):
        """Build a .tap using OSDK build files in temp/ and launch in Oricutron.

        The user must place osdk_config.bat and main.c (from the OSDK
        hires_picture sample) into the temp/ folder.
        make.bat is called from its configured path.
        """
        oricutron = self._require_tool('oricutron_path', 'Oricutron.exe')
        if not oricutron:
            return

        make_bat = self._require_tool('make_bat_path', 'make.bat')
        if not make_bat:
            return

        temp_dir = self._get_temp_dir()

        # Auto-copy emulator build files if enabled
        if CONFIG.get('auto_copy_emu_files', False):
            osdk_root = _derive_osdk_root(CONFIG)
            if osdk_root:
                _copy_emu_sample_files(osdk_root, temp_dir)

        # Check the user has placed the required sample files
        required = ['osdk_config.bat', 'main.c']
        missing = [f for f in required if not os.path.exists(os.path.join(temp_dir, f))]
        if missing:
            messagebox.showerror("Missing build files",
                                 f"The temp folder needs these OSDK files:\n\n"
                                 f"  {', '.join(missing)}\n\n"
                                 f"Copy them from the OSDK hires_picture sample into:\n"
                                 f"  {temp_dir}")
            return

        if not self._ensure_saved():
            return

        # Compile first so the .s file has valid ORIC data
        self.compile_picture()
        if not os.path.exists(self.filename):
            return

        try:
            # Copy the picture .s into temp/ for the build
            shutil.copy2(self.filename, os.path.join(temp_dir, 'picture.s'))

            # Clean previous build output
            build_output = os.path.join(temp_dir, 'BUILD')
            if os.path.isdir(build_output):
                shutil.rmtree(build_output, ignore_errors=True)

            result = subprocess.run(
                ['cmd', '/c',
                 'call', 'osdk_config.bat', '&&',
                 'call', os.path.abspath(make_bat), '%OSDKFILE%'],
                cwd=temp_dir,
                capture_output=True, text=True, timeout=30
            )

            # Find the .tap — name comes from osdk_config.bat (typically HIPIC.tap)
            tap_file = None
            if os.path.isdir(build_output):
                for f in os.listdir(build_output):
                    if f.lower().endswith('.tap'):
                        tap_file = os.path.join(build_output, f)
                        break

            if not tap_file:
                messagebox.showerror("Build Error",
                                     f"OSDK build failed — no .tap produced.\n\n"
                                     f"{result.stdout}\n{result.stderr}")
                return

            # Launch Oricutron from its own dir (needs roms/)
            oricutron_dir = os.path.dirname(oricutron)
            subprocess.Popen(
                [oricutron, '-t', os.path.abspath(tap_file)],
                cwd=oricutron_dir
            )

        except Exception as e:
            messagebox.showerror("Error", f"Build/run failed:\n{e}")

    def compile_picture(self):
        """Export painted colors as PNG, run PictConv -f6 on it, reload result."""
        if not self._ensure_saved():
            return

        Image = self._require_pillow()
        if not Image:
            return

        img = Image.new('RGB', (WIDTH, HEIGHT))
        for y in range(HEIGHT):
            for x in range(WIDTH):
                img.putpixel((x, y), ORIC_RGB.get(self.colors[y][x], (0, 0, 0)))

        abs_filename = os.path.abspath(self.filename)
        tmp_png = os.path.join(self._get_temp_dir(), '_compile_tmp.png')

        try:
            img.save(tmp_png)
            if not self._run_pictconv(tmp_png, abs_filename):
                return
        finally:
            try:
                os.remove(tmp_png)
            except OSError:
                pass

        self.reload()
        messagebox.showinfo("Compiled",
                            "Re-converted using PictConv (Img2Oric algorithm).\n"
                            "Result matches what the ORIC hardware will display.")

    # ---------------------------------------------------------- Save / Load
    def save_picture(self):
        self._do_save()
        self.reload()
        messagebox.showinfo("Saved", f"Saved to {self.filename}")

    def save_as(self):
        """Save current image to a new .s file."""
        path = filedialog.asksaveasfilename(
            title="Save picture as",
            defaultextension=".s",
            filetypes=[("Assembly source", "*.s"), ("All files", "*.*")],
            initialdir=os.path.dirname(os.path.abspath(self.filename)) if self.filename else '.')
        if path:
            self.filename = path
            self._do_save()
            self._update_title()
            messagebox.showinfo("Saved", f"Saved to {self.filename}")

    def _do_save(self):
        """Internal save without dialogs - just write the file."""
        all_new_bytes = []

        for row in range(HEIGHT):
            orig_row = self.raw_data[row] if row < len(self.raw_data) else []
            col = 0
            ink, paper = 7, 0

            for v in orig_row:
                if (v & 0x60) == 0x00:  # Attribute byte
                    attr_type = v & 0x18
                    if attr_type == 0x00:
                        ink = v & 0x07
                    elif attr_type == 0x10:
                        paper = v & 0x07
                    all_new_bytes.append(v)
                    col += 6
                else:  # Pixel byte
                    inv = (v & 0x80) != 0
                    fg = (ink ^ 7) if inv else ink
                    bg = (paper ^ 7) if inv else paper
                    base = 0xC0 if inv else 0x40
                    new_byte = base
                    for bit in range(5, -1, -1):
                        if col < WIDTH:
                            pixel_on = 1 if self.colors[row][col] == fg else 0
                            new_byte |= (pixel_on << bit)
                            col += 1
                    all_new_bytes.append(new_byte)

        new_lines = ["_LabelPicture"]
        for i in range(0, len(all_new_bytes), 16):
            chunk = all_new_bytes[i:i + 16]
            hex_str = ','.join(['$%02x' % b for b in chunk])
            new_lines.append('\t.byt ' + hex_str)

        with open(self.filename, 'w') as f:
            f.write('\n'.join(new_lines))

    def new_picture(self):
        """Create a new blank canvas."""
        if messagebox.askyesno("New Picture", "Create a new blank canvas?\n\nUnsaved changes will be lost."):
            self._init_arrays()
            self._create_blank()
            self.filename = "untitled.s"
            self._update_title()
            self.draw_all()

    def import_image(self):
        """Import an external image (PNG, JPG, BMP) and auto-resize to 240x200."""
        path = filedialog.askopenfilename(
            title="Import image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.gif"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("BMP", "*.bmp"),
                ("All files", "*.*")
            ],
            initialdir=os.path.dirname(os.path.abspath(self.filename)) if self.filename else '.')
        if path:
            self._import_image_file(path)

    def _import_image_file(self, path):
        """Import an image file, resize to 240x200, and convert using PictConv."""
        Image = self._require_pillow()
        if not Image:
            return

        # Ask user where to save the output .s file
        base_name = os.path.splitext(os.path.basename(path))[0]
        output_file = filedialog.asksaveasfilename(
            title="Save imported picture as",
            defaultextension=".s",
            filetypes=[("Assembly source", "*.s"), ("All files", "*.*")],
            initialfile=f"{base_name}.s",
            initialdir=os.path.dirname(os.path.abspath(self.filename)) if self.filename != 'untitled.s' else '.')
        if not output_file:
            return

        tmp_png = os.path.join(self._get_temp_dir(), '_import_tmp.png')
        try:
            img = Image.open(path)
            img = img.convert('RGB')

            orig_w, orig_h = img.size
            scale = min(WIDTH / orig_w, HEIGHT / orig_h)
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)

            img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            final_img = Image.new('RGB', (WIDTH, HEIGHT), (0, 0, 0))
            offset_x = (WIDTH - new_w) // 2
            offset_y = (HEIGHT - new_h) // 2
            final_img.paste(img_resized, (offset_x, offset_y))
            final_img.save(tmp_png)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image:\n{e}")
            return

        try:
            if not self._run_pictconv(tmp_png, output_file):
                return
        finally:
            try:
                os.remove(tmp_png)
            except OSError:
                pass

        # Load the converted file
        self.filename = output_file
        self._update_title()
        self.reload()

        messagebox.showinfo("Imported",
                            f"Image imported and converted to ORIC format.\n\n"
                            f"Saved to: {output_file}\n"
                            f"Original: {orig_w}x{orig_h} -> Resized: {new_w}x{new_h}")

    def load_file(self):
        path = filedialog.askopenfilename(
            title="Open picture data",
            filetypes=[("Assembly source", "*.s"), ("All files", "*.*")],
            initialdir=os.path.dirname(os.path.abspath(self.filename)) if self.filename else '.')
        if path:
            self.filename = path
            self._update_title()
            self.reload()

    def reload(self):
        self._init_arrays()
        if os.path.exists(self.filename):
            self.load_picture()
        else:
            self._create_blank()
        self.draw_all()

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    filename = sys.argv[1] if len(sys.argv) > 1 else None
    OricPictureEditor(filename).run()
