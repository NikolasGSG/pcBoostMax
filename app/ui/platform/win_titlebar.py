"""Apply Windows 11 dark title bar via DWM.

Qt still paints the OS-level title bar using the system theme. On Windows we
can flip the native title bar to dark mode (matching our palette) with a
single ``DwmSetWindowAttribute`` call. Silently no-ops on other platforms.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from ..theme.palette import Palette

# Documented DWM attribute constants.
# 20 is the official public value used since Windows 11 22H2. 19 is the
# legacy value used in early Windows 10 builds.
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_USE_IMMERSIVE_DARK_MODE_LEGACY = 19
_DWMWA_CAPTION_COLOR = 35
_DWMWA_BORDER_COLOR = 34


def _colorref(hex_color: str) -> int:
    """Convert '#RRGGBB' into a Windows COLORREF (0x00BBGGRR)."""
    c = hex_color.lstrip("#")
    r = int(c[0:2], 16)
    g = int(c[2:4], 16)
    b = int(c[4:6], 16)
    return (b << 16) | (g << 8) | r


def apply_dark_titlebar(window, palette: Palette) -> None:
    """Best-effort: turn the OS title bar dark + tinted. No-op off-Windows."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(window.winId())
    except Exception:
        return

    try:
        dwmapi = ctypes.WinDLL("dwmapi")
    except OSError:
        return

    set_attr = dwmapi.DwmSetWindowAttribute
    set_attr.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    set_attr.restype = ctypes.c_long

    # Try the modern attribute first; fall back to the legacy one.
    value = ctypes.c_int(1)
    for attr in (_DWMWA_USE_IMMERSIVE_DARK_MODE, _DWMWA_USE_IMMERSIVE_DARK_MODE_LEGACY):
        result = set_attr(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
        if result == 0:   # S_OK
            break

    # Tint the caption + border to match our surface (only works on Win11 22H2+).
    # Errors here are expected on older builds and we silently ignore them.
    caption = ctypes.c_uint(_colorref(palette.bg_base))
    border = ctypes.c_uint(_colorref(palette.border))
    set_attr(hwnd, _DWMWA_CAPTION_COLOR, ctypes.byref(caption), ctypes.sizeof(caption))
    set_attr(hwnd, _DWMWA_BORDER_COLOR, ctypes.byref(border), ctypes.sizeof(border))
