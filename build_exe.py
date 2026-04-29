"""Build a single-file Windows executable with PyInstaller.

Usage:
    python build_exe.py

Output:
    dist/GameBoostApex.exe
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "main.py"
NAME = "GameBoostApex"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def run(cmd: list[str]) -> None:
    print(">", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> int:
    if not ENTRY.exists():
        print(f"main.py not found at {ENTRY}")
        return 1

    # Clean previous artifacts
    for p in (DIST, BUILD):
        if p.exists():
            shutil.rmtree(p)

    version_file = ROOT / "version_info.txt"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",                       # no console window on launch
        "--name", NAME,
        "--collect-all", "app",
    ]
    if version_file.exists():
        cmd.extend(["--version-file", str(version_file)])
    cmd += [
        # Heavy-but-necessary dependencies PyInstaller's default analysis
        # sometimes misses when the code paths are dynamic:
        "--hidden-import", "psutil",
        "--hidden-import", "PyQt6.sip",
        "--hidden-import", "PyQt6.QtNetwork",   # ad-banner image fetcher
        # Exclude stuff we don't use to shrink the binary:
        "--exclude-module", "tkinter",
        "--exclude-module", "PyQt6.QtQml",
        "--exclude-module", "PyQt6.QtWebEngineCore",
        "--exclude-module", "PyQt6.QtWebEngineWidgets",
        "--exclude-module", "PyQt6.QtMultimedia",
        "--exclude-module", "PyQt6.Qt3DCore",
        "--exclude-module", "matplotlib",
        "--exclude-module", "pandas",
        str(ENTRY),
    ]

    # Include WMI only on Windows — it's optional on other platforms
    if sys.platform == "win32":
        cmd.extend(["--hidden-import", "wmi", "--hidden-import", "win32com.client"])

    run(cmd)

    exe = DIST / f"{NAME}.exe"
    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"\nBuild complete: {exe}  ({size_mb:0.1f} MB)")
        return 0
    print("\nBuild finished but executable not found where expected.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
