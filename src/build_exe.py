#!/usr/bin/env python3
"""
Build standalone executable for ORIC Hires Picture Editor.

Uses PyInstaller to create a single .exe in build/dev or build/release.
The exe uses config.json to find OSDK tools (PictConv.exe, etc.).

Author:  kayto
Version: 1.0 (2024-06)
License: MIT
Part of: ORIC Hires Picture Editor

Requirements:
  pip install pyinstaller pillow

Usage:
  python src/build_exe.py           # Release build (default)
  python src/build_exe.py --dev     # Dev build with console
  python src/build_exe.py --release # Release build (same as default)
"""

import subprocess
import sys
import os
import shutil
import argparse

def main():
    parser = argparse.ArgumentParser(description='Build ORIC Hires Picture Editor executable')
    parser.add_argument('--dev', action='store_true', help='Dev build with console window for debugging')
    parser.add_argument('--release', action='store_true', help='Release build without console (default)')
    args = parser.parse_args()
    
    is_dev = args.dev and not args.release  # --dev unless --release also specified
    build_type = 'dev' if is_dev else 'release'
    
    script_dir = os.path.dirname(os.path.abspath(__file__))  # src/
    project_root = os.path.dirname(script_dir)               # picture_editor/
    build_dir = os.path.join(project_root, 'build', build_type)
    
    # Ensure build directory exists
    os.makedirs(build_dir, exist_ok=True)
    
    # Check for PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)
    
    # Check for Pillow (required by the editor)
    try:
        import PIL
    except ImportError:
        print("Pillow not found. Installing...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'Pillow'], check=True)
    
    # Build the exe
    editor_path = os.path.join(script_dir, 'picture_editor.py')
    
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',                    # Single exe file
        '--console' if is_dev else '--windowed',  # Console for dev, no console for release
        '--name', 'OricHiresPictureEditor',  # Output name
        '--distpath', build_dir,        # Output to build/dev or build/release
        '--workpath', os.path.join(build_dir, 'temp'),
        '--specpath', build_dir,
        '--clean',
        editor_path
    ]
    
    print(f"Building ORIC Hires Picture Editor ({build_type.upper()} build)...")
    print(f"Output: {build_dir}")
    print(f"Command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, cwd=script_dir)
    
    if result.returncode == 0:
        exe_path = os.path.join(build_dir, 'OricHiresPictureEditor.exe')
        
        # Copy config.json template next to the exe
        config_src = os.path.join(project_root, 'config.json')
        config_dst = os.path.join(build_dir, 'config.json')
        if os.path.exists(config_src):
            shutil.copy2(config_src, config_dst)
            print(f"Copied config.json to {build_dir}")
        
        # Create temp/ directory for OSDK build files
        temp_dir = os.path.join(build_dir, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        print(f"Created temp/ directory at {temp_dir}")
        
        # Clean up PyInstaller intermediates
        spec_file = os.path.join(build_dir, 'OricHiresPictureEditor.spec')
        if os.path.exists(spec_file):
            os.remove(spec_file)
        pyinst_temp = os.path.join(build_dir, 'temp', 'OricHiresPictureEditor')
        if os.path.isdir(pyinst_temp):
            shutil.rmtree(pyinst_temp, ignore_errors=True)
        
        print(f"\n{'='*60}")
        print(f"BUILD SUCCESSFUL! ({build_type.upper()})")
        print(f"{'='*60}")
        print(f"\nExecutable: {exe_path}")
        print(f"\nProject structure:")
        print(f"  build/{build_type}/")
        print(f"    OricHiresPictureEditor.exe  <-- Run this")
        print(f"    config.json                 <-- Paths set via Setup button")
        print(f"    temp/                       <-- OSDK build files (auto-copied or manual)")
        if is_dev:
            print(f"\nDev build includes console window for debugging.")
        print(f"\nUse Setup to set OSDK root. Tick auto-copy to populate temp/ automatically.")
    else:
        print("\nBuild failed!")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
