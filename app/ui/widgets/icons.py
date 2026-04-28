"""In-code vector icons, painted from pure Qt primitives.

Avoids shipping an icon font or SVGs — every glyph is drawn programmatically
from simple arcs/rects/lines so it always matches the theme colour.
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap


IconDrawer = Callable[[QPainter, QRectF, QColor], None]


# ------------------------------------------------------------------ primitives
def _stroke(painter: QPainter, color: QColor, width: float = 1.8) -> None:
    pen = QPen(color)
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)


# ------------------------------------------------------------------ individual icons
def draw_dashboard(p: QPainter, r: QRectF, c: QColor) -> None:
    _stroke(p, c)
    w = r.width(); h = r.height()
    # 4-square grid, rounded corners
    cell_w = (w - 6) / 2
    cell_h = (h - 6) / 2
    p.drawRoundedRect(QRectF(r.x(), r.y(), cell_w, cell_h), 2, 2)
    p.drawRoundedRect(QRectF(r.x() + cell_w + 6, r.y(), cell_w, cell_h), 2, 2)
    p.drawRoundedRect(QRectF(r.x(), r.y() + cell_h + 6, cell_w, cell_h), 2, 2)
    p.drawRoundedRect(QRectF(r.x() + cell_w + 6, r.y() + cell_h + 6, cell_w, cell_h), 2, 2)


def draw_bolt(p: QPainter, r: QRectF, c: QColor) -> None:
    path = QPainterPath()
    path.moveTo(r.x() + r.width() * 0.55, r.y())
    path.lineTo(r.x() + r.width() * 0.15, r.y() + r.height() * 0.55)
    path.lineTo(r.x() + r.width() * 0.45, r.y() + r.height() * 0.55)
    path.lineTo(r.x() + r.width() * 0.35, r.y() + r.height())
    path.lineTo(r.x() + r.width() * 0.85, r.y() + r.height() * 0.45)
    path.lineTo(r.x() + r.width() * 0.55, r.y() + r.height() * 0.45)
    path.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    p.drawPath(path)


def draw_controller(p: QPainter, r: QRectF, c: QColor) -> None:
    _stroke(p, c)
    pad = 1.5
    body = QRectF(r.x() + pad, r.y() + r.height() * 0.25, r.width() - pad * 2, r.height() * 0.55)
    p.drawRoundedRect(body, 5, 5)
    # D-pad + button
    cx1 = r.x() + r.width() * 0.3
    cx2 = r.x() + r.width() * 0.72
    cy = r.y() + r.height() * 0.52
    p.drawLine(QPointF(cx1 - 3, cy), QPointF(cx1 + 3, cy))
    p.drawLine(QPointF(cx1, cy - 3), QPointF(cx1, cy + 3))
    p.setBrush(c)
    p.drawEllipse(QPointF(cx2, cy), 2.0, 2.0)


def draw_pulse(p: QPainter, r: QRectF, c: QColor) -> None:
    _stroke(p, c)
    y_mid = r.center().y()
    path = QPainterPath()
    path.moveTo(r.x(), y_mid)
    path.lineTo(r.x() + r.width() * 0.25, y_mid)
    path.lineTo(r.x() + r.width() * 0.35, r.y() + r.height() * 0.2)
    path.lineTo(r.x() + r.width() * 0.5, r.y() + r.height() * 0.8)
    path.lineTo(r.x() + r.width() * 0.62, y_mid)
    path.lineTo(r.x() + r.width(), y_mid)
    p.drawPath(path)


def draw_broom(p: QPainter, r: QRectF, c: QColor) -> None:
    _stroke(p, c)
    # handle
    p.drawLine(
        QPointF(r.x() + r.width() * 0.75, r.y()),
        QPointF(r.x() + r.width() * 0.35, r.y() + r.height() * 0.55),
    )
    # bristle block
    block = QRectF(r.x() + r.width() * 0.15, r.y() + r.height() * 0.45, r.width() * 0.6, r.height() * 0.2)
    p.setBrush(c)
    p.drawRoundedRect(block, 2, 2)
    # bristles
    for i in range(4):
        x = block.x() + i * (block.width() / 4) + 3
        p.setPen(c)
        p.drawLine(QPointF(x, block.bottom()), QPointF(x - 2, r.y() + r.height()))


def draw_shield(p: QPainter, r: QRectF, c: QColor) -> None:
    _stroke(p, c)
    path = QPainterPath()
    path.moveTo(r.center().x(), r.y())
    path.lineTo(r.right(), r.y() + r.height() * 0.22)
    path.lineTo(r.right() - r.width() * 0.1, r.bottom())
    path.lineTo(r.x() + r.width() * 0.1, r.bottom())
    path.lineTo(r.x(), r.y() + r.height() * 0.22)
    path.closeSubpath()
    p.drawPath(path)
    # checkmark
    p.drawLine(
        QPointF(r.x() + r.width() * 0.35, r.center().y()),
        QPointF(r.center().x(), r.y() + r.height() * 0.65),
    )
    p.drawLine(
        QPointF(r.center().x(), r.y() + r.height() * 0.65),
        QPointF(r.right() - r.width() * 0.25, r.y() + r.height() * 0.42),
    )


def draw_gear(p: QPainter, r: QRectF, c: QColor) -> None:
    _stroke(p, c)
    cx, cy = r.center().x(), r.center().y()
    outer = min(r.width(), r.height()) * 0.45
    inner = outer * 0.5
    p.drawEllipse(QPointF(cx, cy), outer * 0.55, outer * 0.55)
    # 8 teeth
    import math
    for i in range(8):
        angle = i * (math.pi * 2 / 8)
        x1 = cx + math.cos(angle) * inner * 1.2
        y1 = cy + math.sin(angle) * inner * 1.2
        x2 = cx + math.cos(angle) * outer
        y2 = cy + math.sin(angle) * outer
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def draw_history(p: QPainter, r: QRectF, c: QColor) -> None:
    _stroke(p, c)
    margin = r.width() * 0.1
    p.drawEllipse(r.adjusted(margin, margin, -margin, -margin))
    cx, cy = r.center().x(), r.center().y()
    p.drawLine(QPointF(cx, cy), QPointF(cx, r.y() + r.height() * 0.25))
    p.drawLine(QPointF(cx, cy), QPointF(cx + r.width() * 0.22, cy))


def draw_eye(p: QPainter, r: QRectF, c: QColor) -> None:
    _stroke(p, c)
    cx, cy = r.center().x(), r.center().y()
    # Almond outline — two symmetric quadratic curves
    path = QPainterPath()
    path.moveTo(r.left() + 1, cy)
    path.quadTo(cx, r.top(), r.right() - 1, cy)
    path.quadTo(cx, r.bottom(), r.left() + 1, cy)
    p.drawPath(path)
    # Pupil
    p.setBrush(c)
    p.drawEllipse(QPointF(cx, cy), r.width() * 0.17, r.width() * 0.17)


def draw_spark(p: QPainter, r: QRectF, c: QColor) -> None:
    """4-pointed star/spark — used by the Insights tab."""
    _stroke(p, c)
    cx, cy = r.center().x(), r.center().y()
    long_r = min(r.width(), r.height()) * 0.45
    short_r = long_r * 0.35
    path = QPainterPath()
    path.moveTo(cx, cy - long_r)
    path.lineTo(cx + short_r, cy - short_r)
    path.lineTo(cx + long_r, cy)
    path.lineTo(cx + short_r, cy + short_r)
    path.lineTo(cx, cy + long_r)
    path.lineTo(cx - short_r, cy + short_r)
    path.lineTo(cx - long_r, cy)
    path.lineTo(cx - short_r, cy - short_r)
    path.closeSubpath()
    p.drawPath(path)


def draw_trophy(p: QPainter, r: QRectF, c: QColor) -> None:
    """Small trophy — Stats / achievements."""
    _stroke(p, c)
    cx = r.center().x()
    top = r.y() + r.height() * 0.1
    cup_h = r.height() * 0.55
    cup_w = r.width() * 0.6
    cup = QRectF(cx - cup_w / 2, top, cup_w, cup_h)
    p.drawRoundedRect(cup, 2, 2)
    # handles
    p.drawArc(QRectF(cup.left() - cup_w * 0.3, cup.top() + cup_h * 0.05,
                     cup_w * 0.3, cup_h * 0.5), 90 * 16, 180 * 16)
    p.drawArc(QRectF(cup.right(), cup.top() + cup_h * 0.05,
                     cup_w * 0.3, cup_h * 0.5), -90 * 16, 180 * 16)
    # stem + base
    stem_top = cup.bottom()
    stem_h = r.height() * 0.18
    p.drawLine(QPointF(cx, stem_top), QPointF(cx, stem_top + stem_h))
    base_w = cup_w * 0.7
    base_y = stem_top + stem_h
    p.drawLine(QPointF(cx - base_w / 2, base_y), QPointF(cx + base_w / 2, base_y))


def draw_wrench(p: QPainter, r: QRectF, c: QColor) -> None:
    """Wrench — Tools tab."""
    _stroke(p, c)
    # Shaft (diagonal line) + circle head with notch
    head_r = min(r.width(), r.height()) * 0.18
    head_cx = r.x() + r.width() * 0.28
    head_cy = r.y() + r.height() * 0.28
    p.drawEllipse(QPointF(head_cx, head_cy), head_r, head_r)
    # notch (small wedge cut)
    p.drawLine(QPointF(head_cx - head_r * 0.4, head_cy - head_r * 0.4),
               QPointF(head_cx + head_r * 0.4, head_cy + head_r * 0.4))
    # shaft
    tail_x = r.x() + r.width() * 0.85
    tail_y = r.y() + r.height() * 0.85
    p.drawLine(QPointF(head_cx + head_r * 0.7, head_cy + head_r * 0.7),
               QPointF(tail_x, tail_y))


# ------------------------------------------------------------------ registry
_ICONS: dict[str, IconDrawer] = {
    "dashboard": draw_dashboard,
    "bolt": draw_bolt,
    "controller": draw_controller,
    "pulse": draw_pulse,
    "broom": draw_broom,
    "shield": draw_shield,
    "gear": draw_gear,
    "history": draw_history,
    "eye": draw_eye,
    "spark": draw_spark,
    "trophy": draw_trophy,
    "wrench": draw_wrench,
}


def pixmap_for(name: str, color: str, size: int = 18) -> QPixmap:
    """Return a transparent QPixmap with the named icon painted in ``color``."""
    drawer = _ICONS.get(name, draw_bolt)
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pad = 2
    drawer(painter, QRectF(pad, pad, size - pad * 2, size - pad * 2), QColor(color))
    painter.end()
    return pm
