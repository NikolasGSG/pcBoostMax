"""Palette presets — alternate looks the user can pick in Settings.

Each preset is a fully-formed :class:`Palette` produced by
:func:`dataclasses.replace` from the canonical "apex" palette so any
field omitted falls back to the obsidian default.

The choice persists to ``AppConfig.theme_preset``.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Tuple

from .palette import Palette


def _apex() -> Palette:
    return Palette()


def _cyber_pink() -> Palette:
    """Magenta + cyan, very neon."""
    return replace(
        Palette(),
        accent="#FF2EC8",
        accent_hover="#FF63D6",
        accent_pressed="#D720A8",
        accent_dim="#330824",
        accent_glow="#FF8DE0",
        bracket="#FF2EC8",
        bracket_dim="#5A0A40",
        glow_lime="#FF8DE0",
        chart_cpu="#FF2EC8",
    )


def _stealth_mono() -> Palette:
    """Pure greyscale — no green at all."""
    return replace(
        Palette(),
        accent="#E0E6EE",
        accent_hover="#FFFFFF",
        accent_pressed="#B7BFCB",
        accent_dim="#1B1F26",
        accent_glow="#FFFFFF",
        neon_blue="#A0AEC0",
        neon_blue_hot="#CBD5E0",
        bracket="#FFFFFF",
        bracket_dim="#3A4250",
        glow_lime="#FFFFFF",
        chart_cpu="#E0E6EE",
        chart_gpu="#A0AEC0",
    )


def _synthwave() -> Palette:
    """Sunset-purple primary, pink accent."""
    return replace(
        Palette(),
        bg_base="#0B0420",
        bg_surface="#1A0B36",
        bg_elevated="#260F4A",
        bg_sunken="#070118",
        accent="#FF8C42",
        accent_hover="#FFB88A",
        accent_pressed="#E66B1F",
        accent_dim="#3A1A07",
        accent_glow="#FFC79E",
        neon_blue="#7B5CFF",
        violet="#FF2EC8",
        bracket="#FF8C42",
        chart_cpu="#FF8C42",
        chart_gpu="#7B5CFF",
        chart_ram="#FF2EC8",
    )


def _arctic() -> Palette:
    """Ice-blue accent, cooler greys."""
    return replace(
        Palette(),
        accent="#7DD3FC",
        accent_hover="#BAE6FD",
        accent_pressed="#38BDF8",
        accent_dim="#0E2B3F",
        accent_glow="#E0F2FE",
        bracket="#7DD3FC",
        bracket_dim="#0E2B3F",
        glow_lime="#E0F2FE",
        chart_cpu="#7DD3FC",
    )


# ---------------------------------------------------------------- registry
PRESETS: Dict[str, Tuple[str, str]] = {
    # id: (display name, blurb)
    "apex":         ("Apex Lime",   "Default — electric lime on obsidian"),
    "cyber_pink":   ("Cyber Pink",  "Magenta neon + cyan"),
    "stealth_mono": ("Stealth Mono", "Greyscale, zero green"),
    "synthwave":    ("Synthwave",   "Sunset orange + purple"),
    "arctic":       ("Arctic",      "Ice blue, cool greys"),
}


_BUILDERS = {
    "apex": _apex,
    "cyber_pink": _cyber_pink,
    "stealth_mono": _stealth_mono,
    "synthwave": _synthwave,
    "arctic": _arctic,
}


def palette_for(preset_id: str) -> Palette:
    """Return the :class:`Palette` for a preset id; falls back to apex."""
    return _BUILDERS.get(preset_id, _apex)()


def preset_ids() -> List[str]:
    return list(PRESETS.keys())


def preset_label(preset_id: str) -> str:
    name, _ = PRESETS.get(preset_id, ("Apex Lime", ""))
    return name


def preset_blurb(preset_id: str) -> str:
    _, blurb = PRESETS.get(preset_id, ("", ""))
    return blurb
