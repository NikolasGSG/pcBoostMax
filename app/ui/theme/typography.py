"""Apex typography — hardware-HUD type system.

Three families are layered:

* **body**     — humanist sans for paragraph copy (Segoe UI → Inter → system).
* **display**  — condensed/extended sans for big readouts (Bahnschrift
  Condensed → Oswald → Inter Display → body fallback).
* **mono**     — mono with tabular figures for FPS / ms / % numerics
  (JetBrains Mono → Cascadia Mono → Consolas).

The condensed display family is what gives the UI its hardware-brand
presence — wide column of code-style figures next to lime/cyan accents.
"""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QFont, QFontDatabase


def _first_available(*candidates: str, fallback: str = "Sans Serif") -> str:
    families = set(QFontDatabase.families())
    for c in candidates:
        if c in families:
            return c
    return fallback


def _preferred_family() -> str:
    return _first_available(
        "Segoe UI Variable", "Segoe UI", "Inter", "SF Pro Text", "Helvetica Neue",
    )


def _display_family() -> str:
    # Condensed display face. Bahnschrift ships with Windows 10/11.
    return _first_available(
        "Bahnschrift Condensed", "Bahnschrift SemiCondensed", "Bahnschrift",
        "Oswald", "Barlow Condensed", "Inter Display",
        fallback=_preferred_family(),
    )


def _mono_family() -> str:
    return _first_available(
        "JetBrains Mono", "Cascadia Mono", "Cascadia Code", "Consolas",
        "Fira Code", "Source Code Pro",
        fallback="Courier New",
    )


@dataclass(frozen=True)
class Typography:
    family: str = ""
    display_family: str = ""
    mono_family: str = ""

    def __post_init__(self) -> None:  # dataclass.frozen workaround
        object.__setattr__(self, "family", self.family or _preferred_family())
        object.__setattr__(self, "display_family", self.display_family or _display_family())
        object.__setattr__(self, "mono_family", self.mono_family or _mono_family())

    # -------- scale (pt) ----------------------------------------------------
    hero_size: int = 48           # massive HUD numerals (FPS readout etc)
    display_size: int = 28        # large readouts (e.g. 78 °C)
    h1_size: int = 22             # page titles
    h2_size: int = 15             # card titles — tighter than v1
    body_size: int = 11           # default text
    small_size: int = 10          # metadata
    micro_size: int = 9           # badges / eyebrows

    # -------- body family ---------------------------------------------------
    def h1(self) -> QFont:
        f = QFont(self.family, self.h1_size)
        f.setWeight(QFont.Weight.DemiBold)
        return f

    def h2(self) -> QFont:
        f = QFont(self.family, self.h2_size)
        f.setWeight(QFont.Weight.Medium)
        return f

    def body(self) -> QFont:
        f = QFont(self.family, self.body_size)
        f.setWeight(QFont.Weight.Normal)
        return f

    def body_strong(self) -> QFont:
        f = QFont(self.family, self.body_size)
        f.setWeight(QFont.Weight.DemiBold)
        return f

    def small(self) -> QFont:
        f = QFont(self.family, self.small_size)
        f.setWeight(QFont.Weight.Normal)
        return f

    def micro(self) -> QFont:
        f = QFont(self.family, self.micro_size)
        f.setWeight(QFont.Weight.DemiBold)
        f.setCapitalization(QFont.Capitalization.AllUppercase)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 116)
        return f

    def eyebrow(self) -> QFont:
        """All-caps, wide letter-spacing, tiny — used as section eyebrows."""
        f = QFont(self.family, self.micro_size)
        f.setWeight(QFont.Weight.Bold)
        f.setCapitalization(QFont.Capitalization.AllUppercase)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 132)
        return f

    # -------- display family (condensed, used for big readouts) -------------
    def hero(self) -> QFont:
        f = QFont(self.display_family, self.hero_size)
        f.setWeight(QFont.Weight.Black)
        return f

    def display(self) -> QFont:
        f = QFont(self.display_family, self.display_size)
        f.setWeight(QFont.Weight.Bold)
        return f

    def display_h1(self) -> QFont:
        """Condensed page title, used in v2 hero panels."""
        f = QFont(self.display_family, self.h1_size)
        f.setWeight(QFont.Weight.Bold)
        f.setCapitalization(QFont.Capitalization.AllUppercase)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 102)
        return f

    # -------- mono family (HUD numerics, ticker) ----------------------------
    def mono(self, size: int | None = None) -> QFont:
        f = QFont(self.mono_family, size or self.body_size)
        f.setWeight(QFont.Weight.Medium)
        f.setStyleStrategy(QFont.StyleStrategy.PreferDefault)
        return f

    def mono_hud(self, size: int | None = None) -> QFont:
        """Bold tabular mono — the FPS / CPU% ticker numerals."""
        f = QFont(self.mono_family, size or self.display_size)
        f.setWeight(QFont.Weight.Bold)
        return f
