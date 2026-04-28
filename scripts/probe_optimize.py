"""Diag: print the widget tree heights for the Optimize view."""
from __future__ import annotations
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QLabel

from app.core.app_controller import AppController
from app.ui.main_window import MainWindow
from app.ui.theme import Theme
from app.ui.widgets.section import SectionHeader


def main() -> int:
    app = QApplication(sys.argv)
    theme = Theme(); theme.apply(app)
    ctrl = AppController()
    w = MainWindow(controller=ctrl, theme=theme)
    w.resize(1280, 820)
    w.show()

    def report():
        w._navigate('optimize')
        opt = w.views['optimize']
        for sh in opt.findChildren(SectionHeader):
            print(f"SectionHeader size={sh.size().width()}x{sh.size().height()} hint={sh.sizeHint().height()}")
            for child in sh.findChildren(QLabel):
                print(f"  Label '{child.text()[:30]}' h={child.size().height()} hint={child.sizeHint().height()} font={child.font().pointSize()}pt")
        # Show the root layout count
        for v in opt.findChildren(QLabel):
            t = v.text()
            if 'OPTIM' in t.upper() or 'REVIEW' in t.upper():
                print(f"Found label '{t[:40]}' geom={v.geometry()}")
        app.quit()

    QTimer.singleShot(800, report)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
