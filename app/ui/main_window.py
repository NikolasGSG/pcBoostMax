"""Main window — owns the sidebar, top bar, stacked views, and analysis orchestration.

Wires the :class:`AppController` singleton to each view's ViewModel and routes
navigation events. Keeps zero business logic itself beyond the analysis
triggered by "Analyze System".
"""
from __future__ import annotations

from typing import Dict, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.app_controller import AppController
from ..core.constants import APP_NAME
from ..overlay.game_detector import GameDetector
from ..overlay.hotkey import GlobalHotkey
from ..overlay.overlay_window import OverlayConfig, OverlayWindow
from ..utils.logger import get_logger
from .platform.win_titlebar import apply_dark_titlebar
from .theme import Theme
from .viewmodels.cleanup_vm import CleanupViewModel
from .viewmodels.game_hub_vm import GameHubViewModel
from .viewmodels.game_mode_vm import GameModeViewModel
from .viewmodels.monitor_vm import MonitorViewModel
from .viewmodels.optimize_vm import OptimizeViewModel
from .views.cleanup_view import CleanupView
from .views.dashboard_view import DashboardView
from .views.game_hub_view import GameHubView
from .views.game_mode_view import GameModeView
from .views.monitor_view import MonitorView
from .views.optimize_view import OptimizeView
from .views.overlay_view import OverlayView, overlay_config_from_app_config
from .views.safety_view import SafetyView
from .views.settings_view import SettingsView
from .widgets.sidebar import NavEntry, Sidebar
from .widgets.ticker_bar import TickerBar
from .widgets.tray_icon import GameBoostTray, tray_icon

log = get_logger("ui.main_window")


_NAV_ENTRIES = [
    NavEntry(id="dashboard", title="Dashboard", icon="dashboard"),
    NavEntry(id="games",     title="Game Hub", icon="controller"),
    NavEntry(id="optimize", title="Optimize", icon="bolt"),
    NavEntry(id="game_mode", title="Game Mode", icon="controller"),
    NavEntry(id="monitor", title="Monitor", icon="pulse"),
    NavEntry(id="insights", title="Insights", icon="spark"),
    NavEntry(id="tools", title="Tools", icon="wrench"),
    NavEntry(id="stats", title="Stats", icon="trophy"),
    NavEntry(id="overlay", title="Overlay", icon="eye"),
    NavEntry(id="cleanup", title="Cleanup", icon="broom"),
    NavEntry(id="safety", title="Safety", icon="shield"),
    NavEntry(id="settings", title="Settings", icon="gear"),
]


class MainWindow(QMainWindow):
    def __init__(self, controller: AppController, theme: Theme, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._ctrl = controller
        self._theme = theme

        self.setWindowTitle(APP_NAME)
        self.resize(1280, 820)
        self.setMinimumSize(1100, 720)

        # ---- ViewModels (MVVM) ------------------------------------------------
        self._monitor_vm = MonitorViewModel(controller, self)
        self._optimize_vm = OptimizeViewModel(controller, self)
        self._game_mode_vm = GameModeViewModel(controller, self)
        self._cleanup_vm = CleanupViewModel(controller, self)
        self._game_hub_vm = GameHubViewModel(controller, self)

        # ---- Shell --------------------------------------------------------
        root = QWidget()
        root.setObjectName("RootSurface")
        self.setCentralWidget(root)

        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar(theme.palette, theme.type, _NAV_ENTRIES)
        self.sidebar.navigated.connect(self._navigate)
        shell.addWidget(self.sidebar)

        # Main area (top bar + stacked views)
        main_area = QVBoxLayout()
        main_area.setContentsMargins(0, 0, 0, 0)
        main_area.setSpacing(0)

        self.top_bar = _TopBar(theme, controller)
        main_area.addWidget(self.top_bar)

        # Live HUD ticker — always-visible CPU/RAM/GPU/Disk/Net pulse
        self.ticker = TickerBar(controller.bus, theme.palette, theme.type)
        main_area.addWidget(self.ticker)

        self.stack = QStackedWidget()
        main_area.addWidget(self.stack, 1)

        main_wrap = QWidget()
        main_wrap.setLayout(main_area)
        main_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        shell.addWidget(main_wrap, 1)

        # ---- Views (lazy) -------------------------------------------------
        # Only build the dashboard up front. All other views are created on
        # first navigation, which roughly halves cold-start time and lets
        # the window paint within ~1s.
        self.views: Dict[str, QWidget] = {}
        self._view_factories: Dict[str, "callable[[], QWidget]"] = {
            "dashboard": self._build_dashboard,
            "games":     self._build_game_hub,
            "optimize":  self._build_optimize,
            "game_mode": self._build_game_mode,
            "monitor":   self._build_monitor,
            "insights":  self._build_insights,
            "tools":     self._build_tools,
            "stats":     self._build_stats,
            "overlay":   self._build_overlay_view,
            "cleanup":   self._build_cleanup,
            "safety":    self._build_safety,
            "settings":  self._build_settings,
        }

        # Default view — built immediately so first paint shows real content.
        self._build_view("dashboard")

        # Default view
        self._navigate("dashboard")

        # Sidebar footer status
        self._update_sidebar_status()

        # Periodic readiness re-scoring — cheap, drives the gauge + headline.
        self._readiness_timer = QTimer(self)
        self._readiness_timer.setInterval(5000)
        self._readiness_timer.timeout.connect(self._update_readiness)
        self._readiness_timer.start()

        # Wire meta signals so the hero chip stays in sync with Game Mode state
        self._game_mode_vm.activated.connect(lambda _s: self._refresh_hero_chips())
        self._game_mode_vm.deactivated.connect(lambda _s: self._refresh_hero_chips())
        self._optimize_vm.plan_applied.connect(lambda _r: self._refresh_hero_chips())

        # Keep the top-bar clock ticking once per second
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self.top_bar.tick_clock)
        self._clock_timer.start()

        self._last_analysis_ts = None

        # ---- Overlay HUD window + global hotkey ----
        # Use the helper so we don't need an OverlayView constructed yet —
        # the view itself can stay lazy.
        self.overlay_window = OverlayWindow(
            palette=theme.palette,
            config=overlay_config_from_app_config(controller.config),
            fps=controller.fps,
            foreground=controller.foreground,
        )

        # Forward every monitor sample into the HUD
        self._monitor_vm.sampled.connect(self.overlay_window.feed_sample)

        # Global hotkey for the HUD
        self._hotkey = GlobalHotkey(callback=self._toggle_overlay)
        self._install_hotkey_from_config()

        # If config had overlay_enabled=True, show it after bootstrap
        if controller.config.overlay_enabled:
            QTimer.singleShot(400, self._show_overlay)

        # ---- System tray icon (always created, visible if supported) ----
        self.setWindowIcon(tray_icon(theme.palette))
        self._tray = GameBoostTray(
            palette=theme.palette,
            on_show=self._tray_show_main,
            on_toggle_game_mode=self._toggle_game_mode_from_tray,
            on_toggle_overlay=self._toggle_overlay,
            on_quit=self._quit_from_tray,
            on_memory_trim=self._tray_memory_trim,
            on_press_to_boost=self._tray_press_to_boost,
            on_run_cleanup=self._tray_run_cleanup,
            parent=self,
        )
        self._tray.show()
        self._force_quit = False  # set to True by the tray "Quit" action

        # ---- Game auto-detect ----
        self._game_detector = GameDetector(controller.foreground, self)
        self._game_detector.game_started.connect(self._on_game_started)
        self._game_detector.game_stopped.connect(self._on_game_stopped)
        self._game_detector.start()

    # ------------------------------------------------------------------ platform polish
    def showEvent(self, event) -> None:  # noqa: D401
        super().showEvent(event)
        # Apply Windows 11 dark title bar after the native window exists.
        apply_dark_titlebar(self, self._theme.palette)

    def closeEvent(self, event) -> None:  # noqa: D401
        # If the tray is available and the user hasn't explicitly quit, hide
        # to tray instead of shutting the app down. This preserves Game Mode
        # auto-detection / HUD behaviour while keeping the main window out of
        # the way.
        if (
            not self._force_quit
            and self._ctrl.config.minimize_to_tray
            and self._tray.isSystemTrayAvailable()
            and self._tray.isVisible()
        ):
            event.ignore()
            self.hide()
            self._tray.notify(
                "GameBoost is still running",
                "We're watching in the background. Double-click the tray icon to return.",
            )
            return

        try:
            self._game_detector.stop()
        except Exception:
            pass
        try:
            self._hotkey.uninstall()
        except Exception:
            pass
        try:
            self.overlay_window.hide_overlay()
            self.overlay_window.deleteLater()
        except Exception:
            pass
        try:
            self._tray.hide()
        except Exception:
            pass
        super().closeEvent(event)

    # ------------------------------------------------------------------ tray + game-detect
    def _tray_show_main(self) -> None:
        """Bring the main window to the foreground from the tray."""
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _toggle_game_mode_from_tray(self) -> None:
        """Toggle Game Mode via the ViewModel (keeps business logic centralised)."""
        try:
            if self._game_mode_vm.is_active:
                self._game_mode_vm.deactivate()
                self._tray.notify("Game Mode OFF", "Reverted to normal operating settings.")
            else:
                self._game_mode_vm.activate()
                self._tray.notify("Game Mode ON", "Applied high-performance settings.")
        except Exception:
            log.exception("Tray Game Mode toggle failed")

    def _quit_from_tray(self) -> None:
        self._force_quit = True
        self.close()
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()

    # ---- v2.1 quick actions -------------------------------------------------
    def _tray_memory_trim(self) -> None:
        try:
            result = self._ctrl.memory_trim.trim()
            self._tray.notify(
                "Memory trimmed",
                f"Freed {result.freed_mb:.0f} MB from {result.trimmed_processes} processes.",
            )
        except Exception:
            log.exception("Tray memory trim failed")

    def _tray_press_to_boost(self) -> None:
        try:
            self._ctrl.boost_burst.start(duration_s=30 * 60)
            self._tray.notify(
                "Press-to-Boost active",
                "Game Mode + 30-minute auto-off engaged.",
            )
        except Exception:
            log.exception("Tray press-to-boost failed")

    def _tray_run_cleanup(self) -> None:
        try:
            scan = self._ctrl.cleanup.scan()
            result = self._ctrl.cleanup.delete(scan.files)
            mb = result.bytes_freed / (1024 * 1024)
            self._tray.notify(
                "Cleanup complete",
                f"Freed {mb:.0f} MB from {result.deleted} files.",
            )
        except Exception:
            log.exception("Tray cleanup failed")

    def _on_game_started(self, game) -> None:
        log.info("Auto-detect: game started — %s", game.exe_name)
        self._tray.set_state_message(f"Game detected: {game.exe_name}")
        cfg = self._ctrl.config
        if cfg.auto_game_mode and not self._game_mode_vm.is_active:
            try:
                self._game_mode_vm.activate()
                self._tray.notify(
                    "Game Mode auto-activated",
                    f"Detected {game.exe_name}. High-performance profile applied.",
                )
            except Exception:
                log.exception("auto Game Mode activate failed")
        if cfg.auto_hud_on_game and not self.overlay_window.isVisible():
            try:
                self._show_overlay()
            except Exception:
                log.exception("auto HUD show failed")

    def _on_game_stopped(self, game) -> None:
        log.info("Auto-detect: game ended — %s", game.exe_name)
        self._tray.set_state_message("running in the background")
        cfg = self._ctrl.config
        if cfg.auto_game_mode and self._game_mode_vm.is_active:
            try:
                self._game_mode_vm.deactivate()
                self._tray.notify(
                    "Game Mode auto-reverted",
                    f"{game.exe_name} closed — restored pre-game settings.",
                )
            except Exception:
                log.exception("auto Game Mode deactivate failed")
        if cfg.auto_hud_on_game and self.overlay_window.isVisible():
            try:
                self._hide_overlay()
            except Exception:
                log.exception("auto HUD hide failed")

    # ------------------------------------------------------------------ view factories
    def _build_view(self, entry_id: str) -> Optional[QWidget]:
        """Run the lazy factory for ``entry_id`` and register the view."""
        if entry_id in self.views:
            return self.views[entry_id]
        factory = self._view_factories.get(entry_id)
        if factory is None:
            log.warning("No factory for view %s", entry_id)
            return None
        view = factory()
        self.views[entry_id] = view
        self.stack.addWidget(view)
        return view

    def _build_dashboard(self) -> QWidget:
        view = DashboardView(self._ctrl, self._monitor_vm, self._theme.palette, self._theme.type)
        view.analyze_requested.connect(lambda: self._navigate("optimize", trigger_analysis=True))
        view.game_mode_requested.connect(lambda: self._navigate("game_mode"))
        view.navigation_requested.connect(self._navigate)
        # Convenience alias used elsewhere in this class
        self.dashboard = view
        return view

    def _build_optimize(self) -> QWidget:
        view = OptimizeView(self._optimize_vm, self._theme.palette, self._theme.type)
        self.optimize = view
        return view

    def _build_game_hub(self) -> QWidget:
        view = GameHubView(self._game_hub_vm, self._theme.palette, self._theme.type)
        self.game_hub = view
        return view

    def _build_game_mode(self) -> QWidget:
        view = GameModeView(self._game_mode_vm, self._theme.palette, self._theme.type)
        self.game_mode = view
        return view

    def _build_monitor(self) -> QWidget:
        view = MonitorView(self._monitor_vm, self._theme.palette, self._theme.type)
        self.monitor = view
        return view

    def _build_insights(self) -> QWidget:
        from .views.insights_view import InsightsView
        view = InsightsView(self._ctrl, self._theme.palette, self._theme.type)
        self.insights = view
        return view

    def _build_tools(self) -> QWidget:
        from .views.tools_view import ToolsView
        view = ToolsView(self._ctrl, self._theme.palette, self._theme.type)
        self.tools = view
        return view

    def _build_stats(self) -> QWidget:
        from .views.stats_view import StatsView
        view = StatsView(self._ctrl, self._theme.palette, self._theme.type)
        self.stats = view
        return view

    def _build_overlay_view(self) -> QWidget:
        view = OverlayView(self._ctrl, self._theme.palette, self._theme.type)
        view.toggle_requested.connect(self._toggle_overlay)
        view.config_changed.connect(self._on_overlay_config_changed)
        # Sync the overlay button label with the live HUD state.
        view.set_overlay_active(self.overlay_window.isVisible())
        self.overlay_view = view
        return view

    def _build_cleanup(self) -> QWidget:
        view = CleanupView(self._cleanup_vm, self._theme.palette, self._theme.type)
        self.cleanup = view
        return view

    def _build_safety(self) -> QWidget:
        view = SafetyView(self._ctrl, self._theme.palette, self._theme.type)
        self.safety = view
        return view

    def _build_settings(self) -> QWidget:
        view = SettingsView(self._ctrl, self._theme.palette, self._theme.type)
        self.settings = view
        return view

    # ------------------------------------------------------------------ navigation
    def _navigate(self, entry_id: str, *, trigger_analysis: bool = False) -> None:
        # Lazy-build the view if this is the first time we're showing it.
        view = self.views.get(entry_id) or self._build_view(entry_id)
        if not view:
            return
        self.sidebar.set_active(entry_id)
        self.top_bar.set_active_entry(entry_id)
        self.stack.setCurrentWidget(view)

        if entry_id == "optimize" and (trigger_analysis or self._optimize_needs_initial_plan()):
            self.optimize.refresh()

        if entry_id == "safety":
            self.safety.refresh()

        log.debug("Navigated to %s", entry_id)

    def _optimize_needs_initial_plan(self) -> bool:
        # Only auto-analyze the first time the user visits this view.
        if getattr(self, "_optimize_seen", False):
            return False
        self._optimize_seen = True
        return True

    # ------------------------------------------------------------------ readiness scoring
    def _update_readiness(self) -> None:
        samples = self._ctrl.monitor.history()
        if not samples:
            return
        snap = self._ctrl.hardware_snapshot
        if not snap:
            return
        bottlenecks = self._ctrl.bottlenecks.analyze(snap, samples)
        # Score = 100 − (severity penalties)
        score = 100.0
        for b in bottlenecks:
            score -= {"info": 5, "warn": 12, "critical": 25}.get(b.severity, 0)
        score = max(0.0, min(100.0, score))
        self.dashboard.set_readiness(score)
        self.dashboard.set_issues(bottlenecks)

        import time as _t

        self._last_analysis_ts = _t.time()
        self._refresh_hero_chips()
        self.top_bar.set_last_analysis(self._last_analysis_ts)

    def _refresh_hero_chips(self) -> None:
        # Last analysis chip
        if self._last_analysis_ts:
            delta = max(0, int(__import__("time").time() - self._last_analysis_ts))
            label = "just now" if delta < 15 else f"{delta}s ago" if delta < 60 else f"{delta // 60}m ago"
            self.dashboard.hero.set_last_analysis(label)
        # Game Mode chip
        self.dashboard.hero.set_game_mode_state(self._game_mode_vm.is_active)

    # ------------------------------------------------------------------ overlay
    def _toggle_overlay(self) -> None:
        if self.overlay_window.isVisible():
            self._hide_overlay()
        else:
            self._show_overlay()

    def _show_overlay(self) -> None:
        self.overlay_window.update_config(overlay_config_from_app_config(self._ctrl.config))
        self.overlay_window.show_overlay()
        self._ctrl.config.update(overlay_enabled=True)
        # Only update the view's button state if the view has been built;
        # if it's still lazy, it will read the live config when constructed.
        view = self.views.get("overlay")
        if view is not None:
            view.set_overlay_active(True)

    def _hide_overlay(self) -> None:
        self.overlay_window.hide_overlay()
        self._ctrl.config.update(overlay_enabled=False)
        view = self.views.get("overlay")
        if view is not None:
            view.set_overlay_active(False)

    def _on_overlay_config_changed(self, config: OverlayConfig) -> None:
        self.overlay_window.update_config(config)
        # Hotkey combo may have changed — reinstall
        self._install_hotkey_from_config()

    def _install_hotkey_from_config(self) -> None:
        c = self._ctrl.config
        ok = self._hotkey.install(
            ctrl=c.overlay_hotkey_ctrl,
            shift=c.overlay_hotkey_shift,
            alt=c.overlay_hotkey_alt,
            key=c.overlay_hotkey_key,
        )
        if not ok:
            log.warning("Failed to install overlay hotkey %s%s%s+%s",
                        "Ctrl+" if c.overlay_hotkey_ctrl else "",
                        "Shift+" if c.overlay_hotkey_shift else "",
                        "Alt+" if c.overlay_hotkey_alt else "",
                        c.overlay_hotkey_key)

    # ------------------------------------------------------------------ top-level bits
    def _update_sidebar_status(self) -> None:
        if self._ctrl.is_admin:
            self.sidebar.set_status(
                "Running with admin privileges · all rules available.",
                admin=True,
            )
        else:
            self.sidebar.set_status(
                "Standard user — restore points and some rules may be skipped. "
                "Launch as admin for full functionality.",
                admin=False,
            )


# ------------------------------------------------------------------ top bar
class _TopBar(QFrame):
    """Thin status strip above the view stack."""

    _LABELS = {
        "dashboard": "Dashboard",
        "optimize": "Optimize",
        "game_mode": "Game Mode",
        "monitor": "Monitor",
        "overlay": "In-Game Overlay",
        "cleanup": "Cleanup",
        "safety": "Safety & History",
        "settings": "Settings",
    }

    def __init__(self, theme: Theme, controller: AppController, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(56)
        self._theme = theme
        self._ctrl = controller
        self._last_analysis_ts: Optional[float] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(32, 0, 32, 0)
        layout.setSpacing(14)

        self._crumbs = QLabel("Dashboard")
        self._crumbs.setFont(theme.type.h2())
        layout.addWidget(self._crumbs)
        layout.addStretch()

        # Last-analysis pill (hidden until a scan has run)
        self._analysis_chip = QLabel("")
        self._analysis_chip.setFont(theme.type.micro())
        self._analysis_chip.setStyleSheet(
            f"color: {theme.palette.text_secondary}; letter-spacing: 1.4px;"
            f"background: {theme.palette.bg_sunken}; border: 1px solid {theme.palette.border};"
            f"border-radius: 10px; padding: 4px 10px;"
        )
        self._analysis_chip.setVisible(False)
        layout.addWidget(self._analysis_chip)

        # Clock pill
        self._clock = QLabel("")
        self._clock.setFont(theme.type.micro())
        self._clock.setStyleSheet(
            f"color: {theme.palette.text_secondary}; letter-spacing: 2.4px;"
            f"background: {theme.palette.bg_sunken}; border: 1px solid {theme.palette.border};"
            f"border-radius: 10px; padding: 4px 10px;"
        )
        layout.addWidget(self._clock)

        # Mode + admin tag on the right
        self._mode = QLabel(f"MODE · {controller.config.mode.upper()}")
        self._mode.setFont(theme.type.micro())
        self._mode.setStyleSheet(f"color: {theme.palette.accent}; letter-spacing: 1.8px;")
        layout.addWidget(self._mode)

        self._admin = QLabel("ADMIN" if controller.is_admin else "USER")
        self._admin.setFont(theme.type.micro())
        admin_color = theme.palette.violet if controller.is_admin else theme.palette.text_tertiary
        self._admin.setStyleSheet(f"color: {admin_color}; letter-spacing: 1.8px;")
        layout.addWidget(self._admin)

        self.tick_clock()

    def set_active_entry(self, entry_id: str) -> None:
        self._crumbs.setText(self._LABELS.get(entry_id, ""))
        self._mode.setText(f"MODE · {self._ctrl.config.mode.upper()}")

    def set_last_analysis(self, ts: float) -> None:
        self._last_analysis_ts = ts
        self._analysis_chip.setVisible(True)
        self.tick_clock()

    def tick_clock(self) -> None:
        import datetime
        import time as _t

        self._clock.setText(datetime.datetime.now().strftime("%H:%M"))
        if self._last_analysis_ts:
            delta = max(0, int(_t.time() - self._last_analysis_ts))
            if delta < 15:
                label = "just now"
            elif delta < 60:
                label = f"{delta}s ago"
            else:
                label = f"{delta // 60}m ago"
            self._analysis_chip.setText(f"ANALYSIS · {label}")

    # Subtle accent strip along the bottom edge for visual separation
    def paintEvent(self, event) -> None:  # noqa: D401
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        color = QColor(self._theme.palette.accent)
        color.setAlpha(45)
        p.fillRect(0, self.height() - 1, self.width(), 1, color)
