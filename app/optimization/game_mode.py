"""Game Mode service.

Activating Game Mode:

    * Captures a "snapshot" of the current system state the user cares about
      (active power plan + visual-effects preset + Game DVR state).
    * Applies a curated subset of rules (power plan + visual effects + DVR).
    * Optionally suspends a user-approved list of heavy background apps.
    * Records *every* change so deactivation restores it — even if the app
      crashes mid-session, rollback is still possible from the action log.

Design notes:

    * We never kill processes. Suspending → resuming keeps the user's work
      (tabs, documents, chat history) intact.
    * Deactivation is idempotent and best-effort: if one restore fails we
      still attempt the rest.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

import psutil

from ..core.config import AppConfig
from ..core.event_bus import EventBus
from ..safety.action_history import ActionHistory, ActionRecord
from ..safety.rollback_engine import RollbackEngine
from ..utils.logger import get_logger
from .rules.game_dvr_rule import GameDVRRule
from .rules.power_plan_rule import PowerPlanRule
from .rules.visual_effects_rule import VisualEffectsRule

log = get_logger("opt.game_mode")


@dataclass
class SuspendedProcess:
    pid: int
    name: str


@dataclass
class GameModeSnapshot:
    """Everything captured at activation time so rollback can restore it."""

    started_at: float
    applied_action_ids: List[str] = field(default_factory=list)
    suspended: List[SuspendedProcess] = field(default_factory=list)


class GameModeService:
    """Orchestrates activation / deactivation. Thread-unsafe by design —
    only ever called from the UI thread in response to a button press."""

    def __init__(
        self,
        bus: EventBus,
        rollback: RollbackEngine,
        history: ActionHistory,
        config: AppConfig,
    ) -> None:
        self.bus = bus
        self.rollback = rollback
        self.history = history
        self.config = config

        # Rules used by Game Mode (lightweight, fully reversible)
        self._rules = {
            "power": PowerPlanRule(),
            "visual": VisualEffectsRule(),
            "dvr": GameDVRRule(),
        }
        for key, rule in self._rules.items():
            if rule.reversible:
                self.rollback.register(rule.id, rule.restore)

        self._snapshot: Optional[GameModeSnapshot] = None
        self._started_at: Optional[float] = None

    # ------------------------------------------------------------------ API
    @property
    def is_active(self) -> bool:
        return self._snapshot is not None

    @property
    def started_at(self) -> Optional[float]:
        return self._started_at

    def activate(
        self,
        *,
        suspend_targets: Optional[List[str]] = None,
        enable_power: bool = True,
        enable_visual: bool = True,
        enable_dvr: bool = True,
    ) -> GameModeSnapshot:
        if self.is_active:
            log.warning("Activate called while Game Mode already active; ignoring")
            return self._snapshot  # type: ignore[return-value]

        snap = GameModeSnapshot(started_at=time.time())
        self._snapshot = snap
        self._started_at = snap.started_at

        selections = [
            (enable_power, self._rules["power"]),
            (enable_visual, self._rules["visual"]),
            (enable_dvr, self._rules["dvr"]),
        ]

        from ..safety.backup_manager import BackupManager  # local import to avoid cycle

        backups = BackupManager()

        for enabled, rule in selections:
            if not enabled:
                continue
            try:
                outcome = rule.apply()
            except Exception as exc:  # pragma: no cover
                log.exception("Game Mode rule %s crashed", rule.id)
                self._record_failure(rule.id, f"{rule.title} failed: {exc}")
                continue
            if not outcome.ok:
                self._record_failure(rule.id, outcome.message)
                continue
            backup_id = None
            if rule.reversible and outcome.backup_payload is not None:
                backup_id = backups.save(rule.id, f"Game Mode: {rule.title}", outcome.backup_payload)
            record = ActionRecord.new(
                category="gamemode",
                action=rule.id,
                summary=f"Game Mode → {rule.title}",
                risk=rule.risk,
                reversible=bool(backup_id),
                status="applied",
                payload={"during": "game_mode"},
                rollback_ref=backup_id,
            )
            self.history.add(record)
            snap.applied_action_ids.append(record.id)

        if suspend_targets:
            snap.suspended = self._suspend_processes(suspend_targets)
            if snap.suspended:
                self.history.add(ActionRecord.new(
                    category="gamemode",
                    action="gamemode.suspend",
                    summary=f"Suspended {len(snap.suspended)} processes",
                    risk="low",
                    reversible=True,
                    status="applied",
                    payload={"processes": [{"pid": p.pid, "name": p.name} for p in snap.suspended]},
                ))

        self.bus.publish("gamemode.activated", snap)
        log.info("Game Mode activated. Applied=%d  Suspended=%d",
                 len(snap.applied_action_ids), len(snap.suspended))
        return snap

    def deactivate(self) -> None:
        if not self.is_active or self._snapshot is None:
            return
        snap = self._snapshot

        # Resume processes first (least likely to fail).
        for proc in snap.suspended:
            try:
                p = psutil.Process(proc.pid)
                p.resume()
                log.debug("Resumed %s (pid=%d)", proc.name, proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                log.info("Process %d (%s) already gone on resume", proc.pid, proc.name)
            except Exception:
                log.exception("Failed resuming %s", proc.name)

        # Roll back the applied actions in reverse order.
        for action_id in reversed(snap.applied_action_ids):
            record = next((r for r in self.history.all() if r.id == action_id), None)
            if record:
                self.rollback.rollback_action(record)

        self.bus.publish("gamemode.deactivated", snap)
        log.info("Game Mode deactivated")

        self._snapshot = None
        self._started_at = None

    # ------------------------------------------------------------------ internals
    def _record_failure(self, rule_id: str, reason: str) -> None:
        self.history.add(ActionRecord.new(
            category="gamemode",
            action=rule_id,
            summary=f"Game Mode rule failed: {reason}",
            risk="safe",
            reversible=False,
            status="failed",
            payload={"reason": reason},
        ))

    @staticmethod
    def _suspend_processes(name_patterns: List[str]) -> List[SuspendedProcess]:
        wanted = {p.lower() for p in name_patterns}
        suspended: List[SuspendedProcess] = []
        for proc in psutil.process_iter(attrs=["name", "pid"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name and name in wanted:
                    proc.suspend()
                    suspended.append(SuspendedProcess(pid=proc.info["pid"], name=name))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception:
                log.debug("Could not suspend %s", proc.info.get("name"), exc_info=True)
        return suspended
