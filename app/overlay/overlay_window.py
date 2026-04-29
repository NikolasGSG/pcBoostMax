"""Always-on-top, frameless gaming HUD.

- Frameless + translucent background
- Stays above fullscreen games with Tool + WindowStaysOnTopHint
- Draggable: click-and-drag anywhere on the HUD to move it
- Optional click-through mode (WS_EX_TRANSPARENT) so mouse passes to game
- Configurable metrics (FPS, CPU%, GPU%, RAM, Net, Disk, frametime, ping)
- Fed by the existing PerformanceMonitor + FpsTracker + ForegroundTracker
"""
from __future__ import annotations

import sys
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

from ..monitoring.performance_monitor import MetricSample
from ..overlay.foreground_tracker import ForegroundApp, ForegroundTracker
from ..overlay.fps_tracker import FpsSample, FpsTracker
from ..ui.theme.palette import Palette
from ..utils.formatting import human_bytes
from ..utils.logger import get_logger

log = get_logger("overlay.window")


@dataclass
class OverlayConfig:
    enabled: bool = False
    position: str = "top-right"    # top-left | top-right | bottom-left | bottom-right
    opacity: int = 85              # 40..100
    click_through: bool = True
    show_fps: bool = True
    show_cpu: bool = True
    show_gpu: bool = True
    show_ram: bool = True
    show_net: bool = True
    show_disk: bool = False
    show_frametime: bool = True
    show_process: bool = True
    compact: bool = False


class OverlayWindow(QWidget):
    """The HUD panel."""

    def __init__(self, palette: Palette, config: OverlayConfig,
                 fps: FpsTracker, foreground: ForegroundTracker) -> None:
        super().__init__(None)
        self._pal = palette
        self._config = config
        self._fps = fps
        self._fg = foreground

        # Painting
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setWindowOpacity(config.opacity / 100.0)

        # Minimal geometry; we auto-resize to fit content each frame
        self.resize(260, 200)

        # State caches
        self._latest_sample: Optional[MetricSample] = None
        self._frametime_history: Deque[float] = deque(maxlen=120)
        self._fps_history: Deque[float] = deque(maxlen=120)

        # Paint-driven repaint timer (10 Hz is enough for HUD work)
        self._tick = QTimer(self)
        self._tick.setInterval(100)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start()

        # Drag tracking
        self._drag_origin: Optional[QPoint] = None

        self._apply_click_through(config.click_through)

    # ------------------------------------------------------------------ public API
    def feed_sample(self, sample: MetricSample) -> None:
        """Receive a MetricSample from the existing monitor thread via the VM."""
        self._latest_sample = sample
        # Feed FPS proxy when PresentMon isn't available so the "FPS" readout
        # has something to graph.
        self._fps.push_proxy(sample.gpu_percent)

    def update_config(self, config: OverlayConfig) -> None:
        self._config = config
        self.setWindowOpacity(config.opacity / 100.0)
        self._apply_click_through(config.click_through)
        self._reposition()
        self.update()

    def show_overlay(self) -> None:
        self._reposition()
        self.show()
        self.raise_()

    def hide_overlay(self) -> None:
        self.hide()

    def toggle(self) -> None:
        if self.isVisible():
            self.hide_overlay()
        else:
            self.show_overlay()

    # ------------------------------------------------------------------ internals
    def _apply_click_through(self, enabled: bool) -> None:
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_NOACTIVATE = 0x08000000
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_style = style | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            if enabled:
                new_style |= WS_EX_TRANSPARENT
            else:
                new_style &= ~WS_EX_TRANSPARENT
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        except Exception:
            log.debug("click-through toggle failed", exc_info=True)

    def _reposition(self) -> None:
        screen = self.screen()
        if not screen:
            return
        geom = screen.availableGeometry()
        margin = 24
        w, h = self.width(), self.height()
        pos = self._config.position
        if pos == "top-left":
            x, y = geom.x() + margin, geom.y() + margin
        elif pos == "bottom-left":
            x, y = geom.x() + margin, geom.y() + geom.height() - h - margin
        elif pos == "bottom-right":
            x, y = geom.x() + geom.width() - w - margin, geom.y() + geom.height() - h - margin
        else:  # top-right (default)
            x, y = geom.x() + geom.width() - w - margin, geom.y() + margin
        self.move(x, y)

    def _on_tick(self) -> None:
        # Keep history of frame times for the graph
        fps_sample = self._fps.latest()
        if fps_sample:
            self._fps_history.append(fps_sample.fps)
            if fps_sample.frametime_ms > 0:
                self._frametime_history.append(fps_sample.frametime_ms)
        # Ensure we stay above fullscreen games. Only raise every ~1s to avoid
        # flicker / excessive window-manager churn.
        self._raise_counter = getattr(self, "_raise_counter", 0) + 1
        if self.isVisible() and self._raise_counter >= 10:
            self.raise_()
            self._raise_counter = 0
        self.update()

    # ------------------------------------------------------------------ drag
    def mousePressEvent(self, event) -> None:  # noqa: D401
        if event.button() == Qt.MouseButton.LeftButton and not self._config.click_through:
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: D401
        if self._drag_origin and not self._config.click_through:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: D401
        self._drag_origin = None

    # ------------------------------------------------------------------ paint
    def paintEvent(self, _event) -> None:  # noqa: D401
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # ---- layout the text block to figure out our size ----
        rows = self._build_rows()
        row_height = 18
        padding_x, padding_y = 14, 12
        heading_h = 18
        graph_h = 30 if (self._config.show_frametime and not self._config.compact) else 0

        fm_value = QFontMetrics(self._font_value())
        max_label = max((fm_value.horizontalAdvance(r[0]) for r in rows), default=60)
        max_value = max((fm_value.horizontalAdvance(r[1]) for r in rows), default=60)
        total_w = max(220, padding_x * 2 + max_label + 22 + max_value)
        total_h = padding_y * 2 + heading_h + 6 + len(rows) * row_height + graph_h
        if self._config.show_process and not self._config.compact:
            total_h += 28

        if (total_w, total_h) != (self.width(), self.height()):
            self.resize(total_w, total_h)
            self._reposition()

        # ---- background ----
        bg = QColor(self._pal.bg_base)
        bg.setAlpha(235)
        border = QColor(self._pal.accent)
        border.setAlpha(140)

        r = self.rect()
        path = QPainterPath()
        path.addRoundedRect(r.adjusted(1, 1, -1, -1).toRectF(), 12, 12)
        p.fillPath(path, QBrush(bg))
        p.setPen(QPen(border, 1.2))
        p.drawPath(path)

        # Thin accent stripe on the left
        p.fillRect(QRect(r.x(), r.y() + 14, 3, r.height() - 28), QColor(self._pal.accent))

        # ---- heading ----
        p.setFont(self._font_heading())
        p.setPen(QColor(self._pal.text_secondary))
        heading_rect = QRect(r.x() + padding_x, r.y() + padding_y - 2, r.width() - padding_x * 2, heading_h)
        src = "PRESENTMON" if self._fps.source == "presentmon" else "HUD"
        p.drawText(heading_rect, Qt.AlignmentFlag.AlignLeft, f"GAMEBOOSTAPEX · {src}")

        # ---- value rows ----
        y = heading_rect.bottom() + 6
        p.setFont(self._font_value())
        for label, value, color in rows:
            # label
            p.setPen(QColor(self._pal.text_tertiary))
            p.drawText(QRect(r.x() + padding_x, y, 52, row_height),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            # value (right-aligned)
            p.setPen(QColor(color))
            p.drawText(QRect(r.x() + padding_x + 52, y,
                             r.width() - padding_x * 2 - 52, row_height),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, value)
            y += row_height

        # ---- frametime sparkline ----
        if graph_h and self._frametime_history:
            graph_rect = QRect(r.x() + padding_x, y + 4, r.width() - padding_x * 2, graph_h - 6)
            self._draw_frametime(p, graph_rect)
            y = graph_rect.bottom() + 4

        # ---- foreground process ----
        if self._config.show_process and not self._config.compact:
            app = self._fg.sample()
            if app:
                text = f"{app.exe_name}  ·  {app.cpu_percent:0.0f}% / {app.ram_mb:0.0f} MB"
            else:
                text = "no foreground app"
            p.setFont(self._font_small())
            p.setPen(QColor(self._pal.text_tertiary))
            p.drawText(QRect(r.x() + padding_x, y, r.width() - padding_x * 2, 20),
                       Qt.AlignmentFlag.AlignLeft, text)

    # ------------------------------------------------------------------ rendering helpers
    def _build_rows(self) -> List[tuple[str, str, str]]:
        s = self._latest_sample
        fps = self._fps.latest()
        rows: List[tuple[str, str, str]] = []

        if self._config.show_fps:
            if fps:
                rows.append(("FPS", f"{fps.fps:0.0f}", self._fps_color(fps.fps)))
            else:
                rows.append(("FPS", "—", self._pal.text_secondary))
        if self._config.show_frametime and fps and fps.frametime_ms:
            rows.append(("ms",  f"{fps.frametime_ms:0.1f}", self._pal.text_primary))
        if self._config.show_cpu:
            rows.append(("CPU", f"{(s.cpu_percent if s else 0):0.0f}%",
                         self._load_color(s.cpu_percent if s else 0)))
        if self._config.show_gpu:
            rows.append(("GPU", f"{(s.gpu_percent if s else 0):0.0f}%",
                         self._load_color(s.gpu_percent if s else 0)))
        if self._config.show_ram and s:
            rows.append(("RAM", f"{s.ram_percent:0.0f}%  ({human_bytes(s.ram_used_bytes)})",
                         self._load_color(s.ram_percent)))
        if self._config.show_net and s:
            total = s.net_up_bps + s.net_down_bps
            rows.append(("NET", f"{human_bytes(total)}/s", self._pal.chart_gpu))
        if self._config.show_disk and s:
            total = s.disk_read_bps + s.disk_write_bps
            rows.append(("DISK", f"{human_bytes(total)}/s", self._pal.chart_disk))
        return rows

    def _draw_frametime(self, p: QPainter, rect: QRect) -> None:
        values = list(self._frametime_history)
        if not values:
            return
        # Clamp to an expected frametime window to avoid collapsing the graph
        lo, hi = 5.0, max(33.0, max(values) + 2)
        step = rect.width() / max(1, len(values) - 1)

        # Background
        bg = QColor(self._pal.bg_sunken)
        bg.setAlpha(140)
        p.fillRect(rect, bg)

        # 16.6 ms (60 Hz) reference line
        ref_y = rect.bottom() - int((16.6 - lo) / (hi - lo) * rect.height())
        p.setPen(QPen(QColor(self._pal.border), 1, Qt.PenStyle.DashLine))
        p.drawLine(rect.left(), ref_y, rect.right(), ref_y)

        # Line
        pen = QPen(QColor(self._pal.accent))
        pen.setWidthF(1.4)
        p.setPen(pen)
        last = None
        for i, v in enumerate(values):
            clamped = min(hi, max(lo, v))
            y = rect.bottom() - int((clamped - lo) / (hi - lo) * rect.height())
            x = rect.left() + int(i * step)
            if last is not None:
                p.drawLine(last[0], last[1], x, y)
            last = (x, y)

    def _fps_color(self, fps: float) -> str:
        if fps >= 120:
            return self._pal.accent
        if fps >= 60:
            return self._pal.chart_cpu
        if fps >= 30:
            return self._pal.amber
        return self._pal.coral

    def _load_color(self, pct: float) -> str:
        if pct >= 90:
            return self._pal.coral
        if pct >= 70:
            return self._pal.amber
        if pct >= 40:
            return self._pal.chart_cpu
        return self._pal.accent

    # ------------------------------------------------------------------ fonts
    def _font_heading(self) -> QFont:
        f = QFont("Segoe UI Variable", 8, QFont.Weight.DemiBold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
        return f

    def _font_value(self) -> QFont:
        return QFont("Cascadia Mono", 11, QFont.Weight.Medium)

    def _font_small(self) -> QFont:
        return QFont("Segoe UI Variable", 8)
