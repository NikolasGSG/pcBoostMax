"""User-authored automation — macros and scheduled actions.

A "macro" is a small JSON-serialisable script of GameBoostApex actions
(apply rule X, trim memory, kill background apps, switch theme, …).
Macros let power users chain operations into one button or hotkey.
"""
from .macro_recorder import (
    DEFAULT_MACROS,
    Macro,
    MacroAction,
    MacroLibrary,
    MacroRunner,
)

__all__ = [
    "DEFAULT_MACROS",
    "Macro",
    "MacroAction",
    "MacroLibrary",
    "MacroRunner",
]
