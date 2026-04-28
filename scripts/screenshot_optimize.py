"""Take an offscreen screenshot of the Optimize view to verify rendering."""
from __future__ import annotations
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from app.core.app_controller import AppController
from app.ui.main_window import MainWindow
from app.ui.theme import Theme


def main() -> int:
    app = QApplication(sys.argv)
    theme = Theme(); theme.apply(app)
    ctrl = AppController()
    w = MainWindow(controller=ctrl, theme=theme)
    w.resize(1280, 820)
    w.show()
    ctrl.bootstrap()

    def shoot(name: str):
        pix = w.grab()
        out = Path(__file__).resolve().parent / f"_shot_{name}.png"
        pix.save(str(out))
        print(f"saved {out}  size={pix.size().width()}x{pix.size().height()}")

    QTimer.singleShot(200, lambda: w._navigate('dashboard'))
    QTimer.singleShot(500, lambda: shoot('dashboard'))
    QTimer.singleShot(800, lambda: w._navigate('optimize'))
    QTimer.singleShot(1100, lambda: shoot('optimize'))
    QTimer.singleShot(1400, lambda: w._navigate('monitor'))
    QTimer.singleShot(1700, lambda: shoot('monitor'))
    QTimer.singleShot(2000, lambda: w._navigate('settings'))
    QTimer.singleShot(2300, lambda: shoot('settings'))
    QTimer.singleShot(2600, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
