"""Spacing and corner-radius scales. Keep every margin / padding on this grid."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Spacing:
    xxs: int = 2
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32
    huge: int = 48


@dataclass(frozen=True)
class Radius:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 20
    pill: int = 999
