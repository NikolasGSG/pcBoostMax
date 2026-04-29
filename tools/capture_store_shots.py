"""Capture Microsoft Store screenshots for every top-level view.

Usage (from project root)::

    python tools/capture_store_shots.py                  # default 1920x1080
    python tools/capture_store_shots.py --size 2560x1440 # higher density
    python tools/capture_store_shots.py --out custom/    # custom output dir

Outputs PNGs into ``store_screenshots/`` (created if absent), one per
view, named ``01_dashboard.png``, ``02_game_hub.png``, etc.

The order matches ``docs/STORE_LISTING.md`` so you can drag the files
straight into Partner Center → Store listings → English → Screenshots
in alphabetical order and the listing previews come out in the order
the marketing copy expects.

This is a developer-only script — it is not packaged with the binary.
It uses the real ``MainWindow`` + ``AppController`` so the shots are
representative; nothing is mocked. The controller's
``bootstrap(async_hardware=False)`` blocks until the hardware snapshot
is in, so the Dashboard cards render with real values.

If you want clean, marketing-friendly screenshots:

  * Set Windows to dark mode before running (the theme adapts).
  * Close other windows so OS chrome doesn't leak in (we capture the
    QWidget render, not the desktop, so this is just paranoia).
  * Run on a 1920x1080+ monitor at 100% DPI scaling. Lower scaling
    keeps the in-app fonts crisp.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PyQt6.QtCore import QSize, QTimer, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

from app.core.app_controller import AppController
from app.ui.main_window import MainWindow
from app.ui.theme import Theme


# View key -> output filename stem. Order is the order Partner Center
# will display them, so this is also the recommended capture order.
SHOTS: list[tuple[str, str]] = [
    ("dashboard", "01_dashboard"),
    ("games",     "02_game_hub"),
    ("optimize",  "03_optimize"),
    ("monitor",   "04_monitor_fps"),
    ("cleanup",   "05_cleanup"),
    ("safety",    "06_safety"),
    ("settings",  "07_settings_autopilot"),
    ("overlay",   "08_overlay_config"),
    ("game_mode", "09_game_mode"),
]


def _parse_size(s: str) -> QSize:
    try:
        w, h = s.lower().split("x")
        return QSize(int(w), int(h))
    except Exception as exc:
        raise argparse.ArgumentTypeError(
            f"--size must be WxH (e.g. 1920x1080), got {s!r}"
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--size", type=_parse_size, default=QSize(1920, 1080),
        help="window dimensions WxH (default 1920x1080)",
    )
    parser.add_argument(
        "--out", type=Path, default=_ROOT / "store_screenshots",
        help="output directory (default ./store_screenshots)",
    )
    parser.add_argument(
        "--settle", type=int, default=600,
        help="ms to wait after navigation before capturing (default 600)",
    )
    parser.add_argument(
        "--monitor-warmup", type=int, default=4000,
        help="ms to spend on the Monitor view so the FPS graph fills "
             "with real samples (default 4000)",
    )
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    theme = Theme()
    theme.apply(app)
    controller = AppController()
    window = MainWindow(controller=controller, theme=theme)
    window.resize(args.size)
    window.show()

    # Block until hardware detection is in so Dashboard cards have real
    # values when we capture the very first shot.
    controller.bootstrap(async_hardware=False)

    captured: list[Path] = []
    errors: list[str] = []

    def capture(view_key: str, stem: str) -> None:
        target = args.out / f"{stem}.png"
        try:
            pixmap = window.grab()
            ok = pixmap.save(str(target), "PNG")
            if not ok:
                raise RuntimeError(f"QPixmap.save returned False for {target}")
            captured.append(target)
            size_kb = target.stat().st_size // 1024
            print(f"  saved {target.name}  ({pixmap.width()}x{pixmap.height()}, {size_kb} KB)")
        except Exception as exc:
            errors.append(f"{view_key}: {exc}")
            print(f"  FAILED to save {view_key}: {exc}")

    def step(i: int = 0) -> None:
        if i >= len(SHOTS):
            QTimer.singleShot(200, app.quit)
            return
        view_key, stem = SHOTS[i]
        try:
            window._navigate(view_key)
            print(f"[{i + 1}/{len(SHOTS)}] view={view_key}")
        except Exception as exc:
            errors.append(f"navigate {view_key}: {exc}")
            print(f"  navigation failed: {exc}")
            QTimer.singleShot(args.settle, lambda: step(i + 1))
            return

        # Monitor view needs extra warmup for the FPS graph to populate
        # with non-zero samples.
        settle = args.monitor_warmup if view_key == "monitor" else args.settle
        QTimer.singleShot(settle, lambda: (capture(view_key, stem),
                                            QTimer.singleShot(150, lambda: step(i + 1))))

    QTimer.singleShot(500, lambda: step(0))
    code = app.exec()
    controller.shutdown()

    print()
    print(f"Captured {len(captured)}/{len(SHOTS)} screenshots into {args.out}")
    if errors:
        print("Errors:")
        for e in errors:
            print(f"  - {e}")
        return 1
    return code


if __name__ == "__main__":
    sys.exit(main())
