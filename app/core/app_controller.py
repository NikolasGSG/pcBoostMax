"""Central application controller.

The controller owns long-lived singletons (event bus, monitor, optimization
engine, safety services) and exposes them to the ViewModels. Views never
reach for these directly — they go through a ViewModel which, in turn,
talks to the controller. This keeps the UI free of business logic.
"""
from __future__ import annotations

from typing import Optional

from ..automation.macro_recorder import MacroLibrary, MacroRunner
from ..cleanup.cleaner import CleanupService
from ..core.boost_burst import BoostBurstService
from ..engagement.achievements import AchievementService
from ..engagement.streaks import StreakService
from ..monitoring.analyzers.anomaly_detector import AnomalyDetector
from ..monitoring.analyzers.predictive_maintenance import PredictiveMaintenance
from ..monitoring.analyzers.stutter_detector import StutterDetector
from ..monitoring.boot_time import BootTimeService
from ..monitoring.daily_report import DailyReportService
from ..monitoring.live_insights import LiveInsightEngine
from ..monitoring.performance_monitor import PerformanceMonitor
from ..monitoring.session_tracker import SessionTracker
from ..optimization.optimization_engine import OptimizationEngine
from ..optimization.game_mode import GameModeService
from ..optimization.service_tweaker import ServiceTweaker
from ..overlay.foreground_tracker import ForegroundTracker
from ..overlay.fps_tracker import FpsTracker
from ..safety.action_history import ActionHistory
from ..safety.backup_manager import BackupManager
from ..safety.restore_point import RestorePointService
from ..safety.rollback_engine import RollbackEngine
from ..system.bottleneck_analyzer import BottleneckAnalyzer
from ..system.hardware_detector import HardwareDetector
from ..system.inspectors import (
    DriverAuditor,
    NvmeHealthInspector,
    PcieLinkInspector,
    RamXmpInspector,
)
from ..system.memory_trim import MemoryTrimService
from ..system.process_tools import (
    BackgroundAppTamer,
    ProcessActionManager,
    ProcessHunter,
)
from ..utils.admin_check import is_admin
from ..utils.logger import get_logger
from ..utils.paths import ensure_app_dirs
from .autopilot import AutoPilotController
from .config import AppConfig
from .event_bus import EventBus


log = get_logger("core.controller")


class AppController:
    """Entry point from the UI into the domain."""

    def __init__(self) -> None:
        ensure_app_dirs()
        self.bus = EventBus()
        self.config = AppConfig.load()
        self.is_admin = is_admin()

        # Safety stack (used by both optimizer and game mode)
        self.history = ActionHistory()
        self.backups = BackupManager()
        self.restore_points = RestorePointService()
        self.rollback = RollbackEngine(backups=self.backups, history=self.history)

        # System insight
        self.hardware = HardwareDetector()
        self.bottlenecks = BottleneckAnalyzer()

        # Live telemetry
        self.monitor = PerformanceMonitor(bus=self.bus)
        self.session_tracker = SessionTracker(bus=self.bus)
        self.live_insights = LiveInsightEngine(bus=self.bus)

        # Domain engines
        self.optimizer = OptimizationEngine(
            bus=self.bus,
            history=self.history,
            backups=self.backups,
            restore_points=self.restore_points,
            config=self.config,
        )
        self.game_mode = GameModeService(
            bus=self.bus,
            rollback=self.rollback,
            history=self.history,
            config=self.config,
        )
        self.cleanup = CleanupService(bus=self.bus, history=self.history, config=self.config)

        # Overlay trackers — cheap, lazy; actual HUD window is created by the UI
        self.foreground = ForegroundTracker()
        self.fps = FpsTracker()

        # ---- v2.1 services -------------------------------------------------
        # System-level — read-only inspectors are stateless, no construction risk.
        self.memory_trim = MemoryTrimService(bus=self.bus, history=self.history)
        self.boost_burst = BoostBurstService(
            self.bus,
            self.history,
            activate_game_mode=lambda: self.game_mode.activate(),
            deactivate_game_mode=lambda: self.game_mode.deactivate(),
            is_game_mode_active=lambda: self.game_mode.is_active,
        )

        # Process tools (ProcessHunter is stateless; manager + tamer share state)
        self.process_hunter = ProcessHunter()
        self.process_actions = ProcessActionManager(history=self.history)
        self.background_tamer = BackgroundAppTamer(manager=self.process_actions)

        # Hardware inspectors (lightweight constructors)
        self.ram_inspector = RamXmpInspector()
        self.pcie_inspector = PcieLinkInspector()
        self.nvme_inspector = NvmeHealthInspector()
        self.driver_auditor = DriverAuditor()

        # Diagnostics + monitoring services
        self.boot_time = BootTimeService()
        self.daily_report = DailyReportService(history=self.history)
        self.service_tweaker = ServiceTweaker(history=self.history)

        # Engagement
        self.streaks = StreakService()
        self.achievements = AchievementService(self.bus)

        # Analyzers (subscribe to the bus on construction)
        self.stutter_detector = StutterDetector(self.bus)
        self.anomaly_detector = AnomalyDetector(self.bus)
        self.predictive_maintenance = PredictiveMaintenance(
            nvme=self.nvme_inspector,
            boot=self.boot_time,
        )

        # Macros
        self.macro_library = MacroLibrary()
        self.macro_runner = MacroRunner(
            optimization_engine=self.optimizer,
            memory_service=self.memory_trim,
            boost_service=self.boost_burst,
            tamer=self.background_tamer,
        )

        # AutoPilot must come last so all dependencies exist when it
        # subscribes to the bus.
        self.autopilot = AutoPilotController(self)

        self._hardware_snapshot: Optional[object] = None

    # ---------------------------------------------------------------- lifecycle
    def bootstrap(self, *, async_hardware: bool = True) -> None:
        """Kick off background workers once the UI is visible.

        Hardware detection runs in a daemon thread by default — it queries
        WMI/registry, which can take 1–2s and would otherwise block the
        first paint. Listeners get the snapshot via the
        ``hardware.detected`` event when it's ready.

        Pass ``async_hardware=False`` for tests / scripts that need a
        synchronous bootstrap (e.g. smoke tests).
        """
        log.info("Bootstrap: admin=%s mode=%s", self.is_admin, self.config.mode)

        # Cheap pieces — start these synchronously so monitoring is live
        # the moment the UI appears.
        self.monitor.start()
        self.fps.start()

        def _detect() -> None:
            try:
                snap = self.hardware.detect()
                self._hardware_snapshot = snap
                self.bus.publish("hardware.detected", snap)
            except Exception:
                log.exception("Hardware detection failed")

        if async_hardware:
            import threading
            t = threading.Thread(target=_detect, name="hw-detect", daemon=True)
            t.start()
        else:
            _detect()

    def shutdown(self) -> None:
        try:
            self.fps.stop()
        except Exception:
            log.exception("FPS tracker shutdown failed")
        try:
            self.monitor.stop()
        except Exception:
            log.exception("Monitor shutdown failed")
        try:
            if self.game_mode.is_active:
                log.warning("Shutting down with Game Mode active — rolling back")
                self.game_mode.deactivate()
        except Exception:
            log.exception("Game Mode rollback on shutdown failed")
        try:
            self.config.save()
        except Exception:
            log.exception("Config save failed on shutdown")

    # ---------------------------------------------------------------- accessors
    @property
    def hardware_snapshot(self):
        return self._hardware_snapshot
