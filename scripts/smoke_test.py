"""Offscreen smoke test — exercises every view and basic flows.

Usage (from project root):
    $env:QT_QPA_PLATFORM="offscreen"; python scripts/smoke_test.py
"""
from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

# Ensure project root is on sys.path when run from scripts/
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
    theme = Theme()
    theme.apply(app)
    controller = AppController()
    window = MainWindow(controller=controller, theme=theme)
    window.show()
    controller.bootstrap(async_hardware=False)

    views = ["dashboard", "games", "optimize", "game_mode", "monitor", "overlay", "cleanup", "safety", "settings"]

    errors: list[str] = []

    def step(i: int = 0) -> None:
        if i >= len(views):
            QTimer.singleShot(200, verify_action_cards)
            return
        try:
            window._navigate(views[i])
            print(f"[{i + 1}/{len(views)}] navigated to {views[i]}")
        except Exception as exc:  # pragma: no cover
            errors.append(f"{views[i]}: {exc}")
            traceback.print_exc()
        QTimer.singleShot(150, lambda: step(i + 1))

    def verify_action_cards() -> None:
        try:
            optimize = window.views["optimize"]
            cards = optimize._cards
            print(f"[verify] Optimize view rendered {len(cards)} action card(s)")
            if cards:
                first = cards[0]
                print(f"[verify] first card: {first.planned.rule.id}  selected={first.is_selected()}")
            safety = window.views["safety"]
            top_level = safety.tree.topLevelItemCount()
            print(f"[verify] Safety history rows: {top_level}")
        except Exception as exc:
            errors.append(f"verify: {exc}")
            traceback.print_exc()
        QTimer.singleShot(200, app.quit)

    QTimer.singleShot(400, lambda: step(0))

    code = app.exec()
    controller.shutdown()

    if errors:
        print("\nERRORS:")
        for e in errors:
            print(" -", e)
        return 1
    print("\nSmoke test passed.")
    return code


if __name__ == "__main__":
    sys.exit(main())
