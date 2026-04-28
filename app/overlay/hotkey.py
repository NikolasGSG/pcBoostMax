"""Register a Windows global hotkey and surface it as a Qt signal.

Uses the native ``RegisterHotKey`` + WM_HOTKEY mechanism through a
``QAbstractNativeEventFilter``. No external hooking required. Gracefully
no-ops on non-Windows platforms.

Usage:
    hotkey = GlobalHotkey(callback=lambda: overlay.toggle())
    hotkey.install(ctrl=True, shift=True, key="F12")
    ...
    hotkey.uninstall()
"""
from __future__ import annotations

import sys
from typing import Callable, Optional

from PyQt6.QtCore import QAbstractNativeEventFilter, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from ..utils.logger import get_logger

log = get_logger("overlay.hotkey")


# Virtual-key codes we actually care about (Windows VK_*)
_VK = {
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
    "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "HOME": 0x24, "END": 0x23, "INSERT": 0x2D, "DELETE": 0x2E,
    "O": 0x4F, "H": 0x48, "G": 0x47, "P": 0x50,
}

MOD_ALT = 0x1
MOD_CTRL = 0x2
MOD_SHIFT = 0x4
MOD_WIN = 0x8
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312


class _HotkeyFilter(QAbstractNativeEventFilter):
    """Intercept WM_HOTKEY messages and forward them to a callback."""

    def __init__(self, hotkey_id: int, callback: Callable[[], None]) -> None:
        super().__init__()
        self._id = hotkey_id
        self._callback = callback

    def nativeEventFilter(self, eventType, message):  # noqa: N802 - Qt signature
        try:
            import ctypes
            import ctypes.wintypes as wt

            msg = ctypes.cast(int(message), ctypes.POINTER(wt.MSG)).contents
            if msg.message == WM_HOTKEY and msg.wParam == self._id:
                try:
                    self._callback()
                except Exception:
                    log.exception("hotkey callback failed")
                return True, 0
        except Exception:
            pass
        return False, 0


class GlobalHotkey(QObject):
    triggered = pyqtSignal()

    def __init__(self, callback: Optional[Callable[[], None]] = None) -> None:
        super().__init__()
        self._callback = callback or (lambda: self.triggered.emit())
        self._id = 0xB055  # arbitrary unique ID
        self._installed = False
        self._filter: Optional[_HotkeyFilter] = None

    # ------------------------------------------------------------------ api
    def install(self, *, ctrl: bool = False, shift: bool = False,
                alt: bool = False, win: bool = False, key: str = "F12") -> bool:
        if sys.platform != "win32":
            return False
        self.uninstall()

        vk = _VK.get(key.upper())
        if vk is None:
            log.warning("Unknown hotkey %r", key)
            return False

        mods = MOD_NOREPEAT
        if ctrl:
            mods |= MOD_CTRL
        if shift:
            mods |= MOD_SHIFT
        if alt:
            mods |= MOD_ALT
        if win:
            mods |= MOD_WIN

        try:
            import ctypes
            user32 = ctypes.windll.user32
            # RegisterHotKey(hwnd=None, id, fsModifiers, vk)
            ok = user32.RegisterHotKey(None, self._id, mods, vk)
            if not ok:
                log.warning("RegisterHotKey failed (err=%s)", ctypes.get_last_error())
                return False
        except Exception:
            log.exception("RegisterHotKey crashed")
            return False

        self._filter = _HotkeyFilter(self._id, lambda: self._fire())
        app = QApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self._filter)
        self._installed = True
        log.info("Global hotkey installed: ctrl=%s shift=%s alt=%s key=%s",
                 ctrl, shift, alt, key)
        return True

    def uninstall(self) -> None:
        if not self._installed:
            return
        try:
            import ctypes
            ctypes.windll.user32.UnregisterHotKey(None, self._id)
        except Exception:
            pass
        app = QApplication.instance()
        if app is not None and self._filter is not None:
            app.removeNativeEventFilter(self._filter)
        self._filter = None
        self._installed = False

    def _fire(self) -> None:
        self.triggered.emit()
        try:
            self._callback()
        except Exception:
            log.exception("hotkey callback failed")
