"""Smoke-test the overlay window and FPS/foreground trackers in isolation."""
from __future__ import annotations

import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from app.core.app_controller import AppController
from app.overlay.overlay_window import OverlayConfig, OverlayWindow
from app.ui.theme import Theme


def main() -> int:
    app = QApplication(sys.argv)
    theme = Theme()
    theme.apply(app)

    ctrl = AppController()
    ctrl.bootstrap()

    cfg = OverlayConfig(enabled=True, position="top-right", opacity=85)
    hud = OverlayWindow(palette=theme.palette, config=cfg,
                        fps=ctrl.fps, foreground=ctrl.foreground)
    hud.show_overlay()

    # Wait for a few monitor samples and feed them
    def pump() -> None:
        s = ctrl.monitor.latest()
        if s:
            hud.feed_sample(s)

    ticker = QTimer()
    ticker.setInterval(300)
    ticker.timeout.connect(pump)
    ticker.start()

    QTimer.singleShot(2500, app.quit)
    code = app.exec()
    ctrl.shutdown()
    print(f"overlay size={hud.size().width()}x{hud.size().height()}  visible={hud.isVisible()}")
    print("Smoke overlay OK")
    return code


if __name__ == "__main__":
    sys.exit(main())
