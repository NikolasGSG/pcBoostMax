"""Share Card Generator — renders a 1200×630 PNG users can post on
Twitter / Reddit / Discord. Watermarked to drive new installs.

Uses ``QPainter`` exclusively so we don't pull a heavy image library.
The output is intentionally simple: dark background, hex pattern,
one-line headline, two stat blocks, and the GameBoost wordmark.

Public entry points:
    * :func:`render_fps_card` — "+28 FPS in CS2"
    * :func:`render_cleanup_card` — "Cleaned 12.3 GB"
    * :func:`render_boost_card` — "Boost activated · 30 min"
"""
from __future__ import annotations

import datetime as dt
import math
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QPointF, Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPen, QPolygonF

from ..ui.theme.palette import Palette
from ..utils.logger import get_logger
from ..utils.paths import BENCHMARKS_DIR, ensure_app_dirs

log = get_logger("engagement.share_cards")

CARD_W, CARD_H = 1200, 630
MARGIN = 60


def _new_image(palette: Palette) -> QImage:
    img = QImage(CARD_W, CARD_H, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(palette.bg_base))
    return img


def _paint_background(p: QPainter, palette: Palette) -> None:
    grad = QLinearGradient(0, 0, CARD_W, CARD_H)
    grad.setColorAt(0.0, QColor(palette.bg_base))
    grad.setColorAt(1.0, QColor(palette.bg_sunken))
    p.fillRect(0, 0, CARD_W, CARD_H, grad)

    # Hex motif — mirrors the in-app aesthetic.
    p.setPen(QPen(QColor(palette.accent_dim), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    cell = 60.0
    rows = int(CARD_H / cell) + 2
    cols = int(CARD_W / cell) + 2
    for r in range(rows):
        for c in range(cols):
            cx = c * cell + (cell / 2 if r % 2 else 0)
            cy = r * cell * 0.866
            poly = QPolygonF([
                QPointF(cx + cell * 0.5 * math.cos(math.radians(60 * i + 30)),
                        cy + cell * 0.5 * math.sin(math.radians(60 * i + 30)))
                for i in range(6)
            ])
            p.drawPolygon(poly)


def _paint_header(p: QPainter, palette: Palette) -> None:
    # Lime accent bar
    p.fillRect(MARGIN, MARGIN, 6, 36, QColor(palette.accent))
    f = QFont("Segoe UI", 18, QFont.Weight.DemiBold)
    p.setFont(f)
    p.setPen(QColor(palette.text_secondary))
    p.drawText(MARGIN + 22, MARGIN + 28, "GAMEBOOST · APEX")


def _paint_footer(p: QPainter, palette: Palette) -> None:
    p.setPen(QColor(palette.text_tertiary))
    p.setFont(QFont("Segoe UI", 14))
    p.drawText(MARGIN, CARD_H - MARGIN, "Free PC tuner for gamers · github.com/NikolasGSG/pcBoostMax")
    today = dt.date.today().strftime("%b %d, %Y")
    p.drawText(CARD_W - MARGIN - 200, CARD_H - MARGIN, today)


def _paint_headline(p: QPainter, palette: Palette, headline: str) -> None:
    p.setPen(QColor(palette.text_primary))
    f = QFont("Segoe UI", 64, QFont.Weight.Bold)
    p.setFont(f)
    rect = QRectF(MARGIN, 130, CARD_W - 2 * MARGIN, 200)
    p.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, headline)


def _paint_stat_block(
    p: QPainter, palette: Palette, x: int, y: int, value: str, label: str,
) -> None:
    p.setPen(QColor(palette.accent))
    p.setFont(QFont("Segoe UI", 56, QFont.Weight.Black))
    p.drawText(x, y, value)
    p.setPen(QColor(palette.text_secondary))
    p.setFont(QFont("Segoe UI", 16, QFont.Weight.DemiBold))
    p.drawText(x, y + 32, label)


def _save(img: QImage, *, kind: str) -> Path:
    ensure_app_dirs()
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = BENCHMARKS_DIR / f"share_{kind}_{ts}.png"
    if not img.save(str(out), "PNG"):
        log.warning("QImage.save failed for %s", out)
    return out


# ---------------------------------------------------------------- public renderers
def render_fps_card(
    *,
    fps_after: float,
    fps_before: Optional[float] = None,
    game: str = "Your Game",
    palette: Optional[Palette] = None,
) -> Path:
    """`+28 FPS in CS2` — exports to ``benchmarks/share_fps_*.png``."""
    pal = palette or Palette()
    img = _new_image(pal)
    p = QPainter(img)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _paint_background(p, pal)
        _paint_header(p, pal)
        delta = (fps_after - fps_before) if fps_before else fps_after
        sign = "+" if (fps_before is not None and delta >= 0) else ""
        headline = f"{sign}{delta:.0f} FPS in {game}" if fps_before is not None else f"{fps_after:.0f} FPS in {game}"
        _paint_headline(p, pal, headline)
        _paint_stat_block(p, pal, MARGIN, 410, f"{fps_after:.0f}", "AFTER GAMEBOOST")
        if fps_before is not None:
            _paint_stat_block(p, pal, MARGIN + 320, 410, f"{fps_before:.0f}", "BEFORE")
        _paint_footer(p, pal)
    finally:
        p.end()
    return _save(img, kind="fps")


def render_cleanup_card(
    *,
    mb_freed: float,
    files_removed: int = 0,
    palette: Optional[Palette] = None,
) -> Path:
    pal = palette or Palette()
    img = _new_image(pal)
    p = QPainter(img)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _paint_background(p, pal)
        _paint_header(p, pal)
        gb = mb_freed / 1024.0
        headline = f"Cleaned {gb:.1f} GB" if gb >= 1 else f"Cleaned {mb_freed:.0f} MB"
        _paint_headline(p, pal, headline)
        _paint_stat_block(p, pal, MARGIN, 410, f"{gb:.1f} GB" if gb >= 1 else f"{mb_freed:.0f} MB",
                          "DISK SPACE FREED")
        if files_removed:
            _paint_stat_block(p, pal, MARGIN + 360, 410, f"{files_removed:,}", "FILES REMOVED")
        _paint_footer(p, pal)
    finally:
        p.end()
    return _save(img, kind="cleanup")


def render_boost_card(
    *,
    duration_s: int,
    fps_avg: Optional[float] = None,
    palette: Optional[Palette] = None,
) -> Path:
    pal = palette or Palette()
    img = _new_image(pal)
    p = QPainter(img)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _paint_background(p, pal)
        _paint_header(p, pal)
        minutes = max(1, duration_s // 60)
        _paint_headline(p, pal, f"Boosted for {minutes} minutes")
        _paint_stat_block(p, pal, MARGIN, 410, f"{minutes} min", "BURST DURATION")
        if fps_avg:
            _paint_stat_block(p, pal, MARGIN + 320, 410, f"{fps_avg:.0f}", "FPS AVG")
        _paint_footer(p, pal)
    finally:
        p.end()
    return _save(img, kind="boost")
