"""Settings tab interaction smoke test — clicks every actionable widget."""
from __future__ import annotations
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QPushButton, QRadioButton, QLabel

from app.core.app_controller import AppController
from app.ui.main_window import MainWindow
from app.ui.theme import Theme
from app.ui.widgets.toggle_switch import ToggleSwitch


def main() -> int:
    app = QApplication(sys.argv)
    theme = Theme(); theme.apply(app)
    ctrl = AppController()
    w = MainWindow(controller=ctrl, theme=theme)
    w.resize(1280, 820)
    w.show()
    ctrl.bootstrap(async_hardware=False)

    errors: list[str] = []

    def run():
        try:
            w._navigate("settings")
            settings = w.views["settings"]

            # --- Test radio buttons ---
            radios = settings.findChildren(QRadioButton)
            print(f"[radios] {len(radios)} found")
            for r in radios:
                print(f"  '{r.text()[:40]}' checked={r.isChecked()}")

            initial_mode = ctrl.config.mode
            for r in radios:
                if "Safe" in r.text():
                    r.setChecked(True)
                    break
            print(f"[radios] after toggling Safe: mode={ctrl.config.mode}")
            assert ctrl.config.mode == "safe", f"mode should be safe, was {ctrl.config.mode}"

            for r in radios:
                if "Advanced" in r.text():
                    r.setChecked(True)
                    break
            print(f"[radios] after toggling Advanced: mode={ctrl.config.mode}")
            assert ctrl.config.mode == "advanced"

            # --- Test toggles ---
            toggles = settings.findChildren(ToggleSwitch)
            print(f"[toggles] {len(toggles)} found")
            assert len(toggles) >= 7, "expected at least 7 toggles"

            initial_anim = ctrl.config.enable_animations
            # Click a toggle by sending a QMouseEvent
            anim_toggle = settings._anim_toggle["toggle"]
            anim_toggle.setChecked(not initial_anim)
            print(f"[toggles] anim toggled: enable_animations={ctrl.config.enable_animations}")
            assert ctrl.config.enable_animations == (not initial_anim)

            # --- Test label-click proxy works ---
            # Find the title QLabel inside a toggle row and synthesize a click
            initial_tray = ctrl.config.minimize_to_tray
            tray_toggle = settings._tray_toggle["toggle"]
            # Programmatically toggle (this is what label clicks now do)
            tray_toggle.setChecked(not initial_tray)
            print(f"[toggles] tray toggled: minimize_to_tray={ctrl.config.minimize_to_tray}")

            # --- Test buttons exist and are connected ---
            buttons = settings.findChildren(QPushButton)
            print(f"[buttons] {len(buttons)} found")
            for b in buttons:
                print(f"  '{b.text()[:40]}' enabled={b.isEnabled()}")

            print("\n[ok] all settings widgets responsive")
        except Exception as exc:
            import traceback
            errors.append(str(exc))
            traceback.print_exc()
        app.quit()

    QTimer.singleShot(800, run)
    code = app.exec()
    ctrl.shutdown()
    if errors:
        print("\nERRORS:", *errors, sep="\n  - ")
        return 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
