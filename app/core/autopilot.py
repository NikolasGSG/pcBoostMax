"""AutoPilot — the hands-free automation brain.

When AutoPilot is on, the app stops asking. It does the right thing
silently:

1. **Boot pass** — on app start, if a Recommended plan hasn't been applied
   in the last 24h, it silently applies the safe-tier rules of the
   Recommended preset (no admin-only rules without admin; no advisory-only).

2. **Game pass** — when the GameDetector reports a fullscreen game, the
   per-game profile is applied (or a sane default profile if the game has
   no custom profile yet). When the game stops, the per-game profile is
   rolled back so the system returns to the "between sessions" baseline.

3. **Insight pass** — when the LiveInsightEngine reports a CRITICAL
   insight that has a known *safe* automatic resolution (e.g. switch
   power plan), AutoPilot acts on it. Anything ambiguous is left to
   surface as a normal user-facing suggestion.

The goal is "you never have to think about it" without ever doing
anything destructive, and *with everything reversible* via the same
RollbackEngine the manual flow uses.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING, Optional

from ..utils.logger import get_logger
from .event_bus import EventBus

if TYPE_CHECKING:
    from .app_controller import AppController
    from ..monitoring.live_insights import Insight

log = get_logger("core.autopilot")


# Insight ids that are safe to auto-resolve (we know the action is reversible
# and low-risk). Everything else is left to the user.
_SAFE_AUTO_INSIGHTS: frozenset[str] = frozenset({
    "cpu.sustained_pressure",   # we just nudge to High Performance
    "system.healthy_idle",      # apply Recommended if not already applied
})


@dataclass
class AutoPilotStatus:
    enabled: bool = False
    last_boot_apply_ts: Optional[float] = None
    last_game_apply_ts: Optional[float] = None
    last_insight_apply_ts: Optional[float] = None
    actions_today: int = 0


class AutoPilotController:
    """Listens on the bus and silently applies safe automations."""

    EVENT_TOPIC = "autopilot.status"

    # Don't reapply the boot pass more often than this (seconds)
    _BOOT_PASS_COOLDOWN = 60 * 60 * 24      # 1 day
    # Insights are debounced so we don't ping the same fix twice per minute
    _INSIGHT_COOLDOWN = 60

    def __init__(self, controller: "AppController") -> None:
        self._ctrl = controller
        self._bus: EventBus = controller.bus
        self._cfg = controller.config
        self._status = AutoPilotStatus(enabled=self._cfg.autopilot_enabled)
        self._lock = Lock()
        self._last_insight_apply: dict[str, float] = {}

        # Subscriptions are always installed; the *enabled* check is done
        # inside each handler so the user can toggle live without rewiring.
        self._bus.subscribe("hardware.detected", lambda _s: self._maybe_boot_pass())
        self._bus.subscribe("game.started", self._on_game_started)
        self._bus.subscribe("game.stopped", self._on_game_stopped)
        self._bus.subscribe("insights.updated", self._on_insights)

    # ------------------------------------------------------------------ api
    @property
    def status(self) -> AutoPilotStatus:
        return self._status

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._status.enabled = enabled
            self._cfg.autopilot_enabled = enabled
            self._cfg.save()
            self._publish()
        log.info("AutoPilot %s", "ENABLED" if enabled else "DISABLED")
        if enabled:
            # Re-trigger boot pass if it's stale.
            self._maybe_boot_pass()

    # ------------------------------------------------------------------ internal
    def _publish(self) -> None:
        self._bus.publish(self.EVENT_TOPIC, self._status)

    def _maybe_boot_pass(self) -> None:
        if not self._status.enabled or not self._cfg.autopilot_apply_recommended:
            return
        with self._lock:
            last = self._status.last_boot_apply_ts or 0
            if time.time() - last < self._BOOT_PASS_COOLDOWN:
                return
        try:
            applied = self._silent_apply_recommended()
            if applied:
                self._status.last_boot_apply_ts = time.time()
                self._status.actions_today += 1
                self._publish()
                self._bus.publish(
                    "autopilot.acted",
                    {"reason": "boot", "actions": applied},
                )
                log.info("AutoPilot boot pass applied %d action(s)", applied)
        except Exception:
            log.exception("AutoPilot boot pass failed")

    def _silent_apply_recommended(self) -> int:
        """Generate a Recommended plan and apply only the SAFE-tier rules."""
        snapshot = self._ctrl.hardware_snapshot or self._ctrl.hardware.detect()
        plan = self._ctrl.optimizer.generate_plan(snapshot)
        if plan is None or not plan.actions:
            return 0

        # Filter: only safe-risk, non-advisory, applicable, not requiring admin
        # (unless we're elevated)
        from ..core.constants import RISK_SAFE
        safe = []
        for a in plan.actions:
            evaluation = getattr(a, "evaluation", None)
            if evaluation is None or not evaluation.applicable:
                continue
            if getattr(a.rule, "advisory", False):
                continue
            if a.rule.risk != RISK_SAFE:
                continue
            if a.rule.requires_admin and not self._ctrl.is_admin:
                continue
            a.selected = True
            safe.append(a)
        # Deselect everything else so apply_plan only touches our subset
        for a in plan.actions:
            if a not in safe:
                a.selected = False
        if not safe:
            return 0
        self._ctrl.optimizer.bind_rollback(self._ctrl.rollback)
        report = self._ctrl.optimizer.apply_plan(
            plan, create_restore_point=False,
        )
        return len(getattr(report, "results", []) or safe)

    # ------------------------------------------------------------------ game hooks
    def _on_game_started(self, payload: dict | None = None) -> None:
        if not self._status.enabled or not self._cfg.autopilot_per_game_profiles:
            return
        try:
            from ..games.profiles import GameProfileService
            svc = GameProfileService.get(self._ctrl)
            if not svc:
                return
            game_name = (payload or {}).get("name") or ""
            exe = (payload or {}).get("exe") or ""
            applied = svc.apply_for(name=game_name, exe=exe)
            if applied:
                self._status.last_game_apply_ts = time.time()
                self._status.actions_today += 1
                self._publish()
                self._bus.publish("autopilot.acted",
                                  {"reason": "game_start", "game": game_name})
                log.info("AutoPilot applied profile for %s", game_name)
        except Exception:
            log.exception("AutoPilot game-start hook failed")

    def _on_game_stopped(self, payload: dict | None = None) -> None:
        if not self._status.enabled or not self._cfg.autopilot_per_game_profiles:
            return
        try:
            from ..games.profiles import GameProfileService
            svc = GameProfileService.get(self._ctrl)
            if svc:
                svc.restore_baseline()
                log.info("AutoPilot restored baseline after game exit")
        except Exception:
            log.exception("AutoPilot game-stop hook failed")

    # ------------------------------------------------------------------ insights
    def _on_insights(self, insights: list["Insight"]) -> None:
        if not self._status.enabled or not self._cfg.autopilot_act_on_insights:
            return
        from ..monitoring.live_insights import SEVERITY_CRIT
        for ins in insights or []:
            if ins.severity != SEVERITY_CRIT:
                continue
            if ins.id not in _SAFE_AUTO_INSIGHTS:
                continue
            now = time.time()
            last = self._last_insight_apply.get(ins.id, 0)
            if now - last < self._INSIGHT_COOLDOWN:
                continue
            try:
                if self._handle_safe_insight(ins):
                    self._last_insight_apply[ins.id] = now
                    self._status.last_insight_apply_ts = now
                    self._status.actions_today += 1
                    self._publish()
                    self._bus.publish(
                        "autopilot.acted",
                        {"reason": "insight", "id": ins.id},
                    )
                    log.info("AutoPilot resolved insight: %s", ins.id)
            except Exception:
                log.exception("AutoPilot insight handler crashed for %s", ins.id)

    def _handle_safe_insight(self, ins: "Insight") -> bool:
        """Map a safe-auto insight id → a concrete reversible action."""
        if ins.id == "cpu.sustained_pressure":
            return self._silent_apply_recommended() > 0
        if ins.id == "system.healthy_idle":
            # Healthy idle is the perfect time to apply the Recommended plan
            # if we haven't already today.
            return self._silent_apply_recommended() > 0
        return False
