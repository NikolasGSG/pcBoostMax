"""Profile cold startup time of the app to find optimisation targets."""
from __future__ import annotations
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def stamp(label: str, t0: float) -> float:
    now = time.perf_counter()
    print(f"  +{(now - t0)*1000:7.1f} ms  {label}")
    return now


def main() -> int:
    t0 = time.perf_counter()
    last = t0

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    last = stamp("import PyQt6", last)

    app = QApplication(sys.argv)
    last = stamp("QApplication()", last)

    from app.ui.theme import Theme
    last = stamp("import Theme", last)

    theme = Theme(); theme.apply(app)
    last = stamp("Theme.apply", last)

    from app.core.app_controller import AppController
    last = stamp("import AppController", last)

    ctrl = AppController()
    last = stamp("AppController()", last)

    from app.ui.main_window import MainWindow
    last = stamp("import MainWindow", last)

    w = MainWindow(controller=ctrl, theme=theme)
    last = stamp("MainWindow()", last)

    w.resize(1280, 820); w.show()
    last = stamp("show()", last)

    ctrl.bootstrap()
    last = stamp("bootstrap()", last)

    print(f"\n  TOTAL: {(time.perf_counter() - t0)*1000:.1f} ms to first paint")

    QTimer.singleShot(50, app.quit)
    code = app.exec()
    ctrl.shutdown()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
