"""GameBoostApex Optimizer — entry point.

Launches the PyQt6 application, wires up the controller, viewmodels and
the main window. Business logic lives in ``app.core`` and its siblings;
this file is intentionally thin.

When invoked with ``--cli`` (anywhere in argv) we hand off to
:mod:`app.cli` and never instantiate Qt — that lets the CLI be used in
SSH sessions, scripts, and CI without DLL surprises.
"""
from __future__ import annotations

import sys
import traceback


def _cli_invoked(argv: list[str]) -> bool:
    return "--cli" in argv


# Short-circuit BEFORE importing Qt so the CLI works without a display.
if _cli_invoked(sys.argv):
    import os

    # PyInstaller is invoked with --windowed for a clean GUI launch (no
    # flashing console). That detaches stdout/stderr from any terminal,
    # so a CLI invocation of the bundled binary would print to nowhere.
    # Re-attach to the parent process's console (PowerShell, cmd.exe,
    # Windows Terminal) so `gameboostapex.exe --cli ...` works as expected.
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        try:
            import ctypes
            ATTACH_PARENT_PROCESS = -1
            if ctypes.windll.kernel32.AttachConsole(ATTACH_PARENT_PROCESS):
                sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
                sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
                sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
        except Exception:
            # Headless / no parent console (scheduled task, service): fall
            # through silently. Output will go nowhere, but exit code is
            # still set correctly.
            pass

    from app.cli import run_cli
    from app.utils.logger import configure_logging
    configure_logging()
    # Strip the --cli flag so argparse's subparsers don't see it.
    _filtered = [a for a in sys.argv[1:] if a != "--cli"]
    _rc = run_cli(_filtered)
    # PyInstaller-built binaries load Qt's DLLs into the process regardless
    # of whether Python imported PyQt6, and Qt's destructors fastfail
    # (STATUS_STACK_BUFFER_OVERRUN, 0xC0000409) during interpreter teardown.
    # Bypass Python's atexit + GC to exit cleanly with the real return code.
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(_rc if _rc is not None else 0)


from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMessageBox

from app.core.app_controller import AppController
from app.core.constants import APP_NAME, APP_VERSION, ORG_NAME
from app.ui.main_window import MainWindow
from app.ui.theme import Theme
from app.ui.widgets.welcome_dialog import WelcomeDialog
from app.utils.logger import configure_logging, get_logger


def _install_excepthook(log):
    def _hook(exc_type, exc, tb):
        log.critical("Unhandled exception: %s", "".join(traceback.format_exception(exc_type, exc, tb)))
        try:
            QMessageBox.critical(
                None,
                f"{APP_NAME} — Unexpected Error",
                f"An unexpected error occurred:\n\n{exc_type.__name__}: {exc}\n\n"
                "The application will continue running. Check the log for details.",
            )
        except Exception:
            pass

    sys.excepthook = _hook


def main() -> int:
    configure_logging()
    log = get_logger("main")
    log.info("Starting %s v%s", APP_NAME, APP_VERSION)

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORG_NAME)
    app.setStyle("Fusion")  # neutral base — our QSS fully overrides visuals
    # Keep the app alive when the main window is hidden to the system tray.
    app.setQuitOnLastWindowClosed(False)

    # Base font — prefer modern system font, scale sensibly.
    base_font = QFont("Segoe UI Variable", 10)
    if not base_font.exactMatch():
        base_font = QFont("Segoe UI", 10)
    app.setFont(base_font)

    # Construct controller first so we can read the theme preset from config.
    _install_excepthook(log)
    controller = AppController()

    theme = Theme(preset=controller.config.theme_preset)
    theme.apply(app)

    # First-run welcome / disclaimer — explains what the app does, lists the
    # safety guarantees, and warns about SmartScreen. Persists acceptance so
    # the user only sees it once.
    if not controller.config.accepted_disclaimer:
        welcome = WelcomeDialog(
            palette=theme.palette,
            typography=theme.type,
            is_admin=controller.is_admin,
        )
        if welcome.exec() != welcome.DialogCode.Accepted:
            log.info("User declined the disclaimer — exiting.")
            return 0
        controller.config.update(accepted_disclaimer=True)

    window = MainWindow(controller=controller, theme=theme)
    window.show()

    controller.bootstrap()  # kick off background workers after the window is visible

    try:
        return app.exec()
    finally:
        log.info("Shutting down %s", APP_NAME)
        controller.shutdown()


if __name__ == "__main__":
    sys.exit(main())
