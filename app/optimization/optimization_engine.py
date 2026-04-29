"""Optimization engine.

Holds the list of :class:`OptimizationRule` instances, evaluates them against
the current :class:`HardwareSnapshot`, and applies the subset the user picks.

Every apply goes through the safety stack:
    1. (optional) restore point via ``RestorePointService``
    2. capture backup via ``BackupManager``
    3. rule.apply()
    4. record via ``ActionHistory`` + register restorer with ``RollbackEngine``
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from ..core.config import AppConfig
from ..core.event_bus import EventBus
from ..safety.action_history import ActionHistory, ActionRecord
from ..safety.backup_manager import BackupManager
from ..safety.restore_point import RestorePointService
from ..system.hardware_detector import HardwareSnapshot
from ..utils.logger import get_logger
from .rules.advanced_perf_rules import (
    MemoryCompressionOffRule,
    MouseAccelerationOffRule,
    NduServiceOffRule,
    ScheduledTasksBloatRule,
    Win32PrioritySeparationRule,
)
from .rules.background_apps_rule import BackgroundAppsRule
from .rules.base_rule import OptimizationRule, RuleEvaluation
from .rules.game_dvr_rule import GameDVRRule
from .rules.laptop_absolute_rules import (
    BatterySaverOffRule,
    DcMatchesAcRule,
    GpuPreferMaxPerfRule,
    MmcssGamesBoostRule,
    PcieAspmOffRule,
    PowerThrottlingOffRule,
    SystemResponsivenessRule,
    UsbSelectiveSuspendOffRule,
)
from .rules.max_performance_rules import (
    DisableCoreParkingRule,
    DisableFullscreenOptimizationsRule,
    DisableSearchIndexerRule,
    DisableSysMainRule,
    DisableTelemetryRule,
    HagsRule,
    MinProcessorStateRule,
    NagleOffRule,
    TimerResolutionRule,
    UltimatePerformancePlanRule,
    VisualPerformanceModeRule,
)
from .rules.power_plan_rule import PowerPlanRule
from .rules.startup_rule import StartupProgramsRule
from .rules.temp_cleanup_rule import TempCleanupRule
from .rules.visual_effects_rule import VisualEffectsRule

log = get_logger("opt.engine")


# ---------------------------------------------------------------- plan models
@dataclass
class PlannedAction:
    rule: OptimizationRule
    evaluation: RuleEvaluation
    selected: bool = True

    @property
    def title(self) -> str:
        return self.rule.title


@dataclass
class OptimizationPlan:
    hardware: HardwareSnapshot
    actions: List[PlannedAction] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    @property
    def expected_score(self) -> int:
        """Aggregate impact of currently selected actions (0-100)."""
        selected = [a for a in self.actions if a.selected]
        if not selected:
            return 0
        return min(100, int(sum(a.evaluation.score for a in selected) / len(selected) * 1.4))


@dataclass
class RuleApplyResult:
    """Fine-grained per-rule result surfaced in the UI."""
    rule_id: str
    title: str
    status: str                # "applied" | "failed" | "needs_reboot" | "not_verified"
    detail: str = ""
    admin_required: bool = False


@dataclass
class ApplyReport:
    applied: List[ActionRecord] = field(default_factory=list)
    failed: List[tuple[str, str]] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    restore_point_created: bool = False
    restore_point_reason: str = ""
    results: List[RuleApplyResult] = field(default_factory=list)


# ---------------------------------------------------------------- engine
class OptimizationEngine:
    def __init__(
        self,
        bus: EventBus,
        history: ActionHistory,
        backups: BackupManager,
        restore_points: RestorePointService,
        config: AppConfig,
    ) -> None:
        self.bus = bus
        self.history = history
        self.backups = backups
        self.restore_points = restore_points
        self.config = config
        self.rules: List[OptimizationRule] = self._default_rules()
        self._by_id: Dict[str, OptimizationRule] = {r.id: r for r in self.rules}

    # ------------------------------------------------------------------ registration
    @staticmethod
    def _default_rules() -> List[OptimizationRule]:
        return [
            # --- core / baseline rules ---
            PowerPlanRule(),
            VisualEffectsRule(),
            GameDVRRule(),
            BackgroundAppsRule(),
            StartupProgramsRule(),
            TempCleanupRule(),
            # --- "Unleash" high-impact pack ---
            UltimatePerformancePlanRule(),
            DisableCoreParkingRule(),
            MinProcessorStateRule(),
            HagsRule(),
            DisableFullscreenOptimizationsRule(),
            DisableSysMainRule(),
            DisableSearchIndexerRule(),
            DisableTelemetryRule(),
            NagleOffRule(),
            VisualPerformanceModeRule(),
            TimerResolutionRule(),
            # --- "Absolute Performance" (laptop-focused) ---
            PcieAspmOffRule(),
            UsbSelectiveSuspendOffRule(),
            PowerThrottlingOffRule(),
            DcMatchesAcRule(),
            SystemResponsivenessRule(),
            MmcssGamesBoostRule(),
            BatterySaverOffRule(),
            GpuPreferMaxPerfRule(),
            # --- Advanced performance (foreground boost, bloat cleanup) ---
            Win32PrioritySeparationRule(),
            MemoryCompressionOffRule(),
            NduServiceOffRule(),
            MouseAccelerationOffRule(),
            ScheduledTasksBloatRule(),
        ]

    def rule(self, rule_id: str) -> Optional[OptimizationRule]:
        return self._by_id.get(rule_id)

    # ------------------------------------------------------------------ planning
    def generate_plan(self, hardware: HardwareSnapshot) -> OptimizationPlan:
        plan = OptimizationPlan(hardware=hardware)
        for rule in self.rules:
            try:
                evaluation = rule.evaluate(hardware)
            except Exception:
                log.exception("Rule %s evaluation crashed", rule.id)
                continue
            if evaluation.applicable:
                plan.actions.append(PlannedAction(rule=rule, evaluation=evaluation, selected=True))
        # Sort by score desc so the user sees the biggest wins first
        plan.actions.sort(key=lambda a: a.evaluation.score, reverse=True)
        log.info("Plan generated with %d applicable rules", len(plan.actions))
        self.bus.publish("opt.plan_ready", plan)
        return plan

    # ------------------------------------------------------------------ execution
    def apply_plan(self, plan: OptimizationPlan, create_restore_point: Optional[bool] = None) -> ApplyReport:
        report = ApplyReport()
        selected = [a for a in plan.actions if a.selected]
        if not selected:
            log.info("No actions selected — nothing to apply")
            return report

        want_rp = self.config.create_restore_point if create_restore_point is None else create_restore_point
        if want_rp:
            res = self.restore_points.create("GameBoostApex: before optimization plan")
            report.restore_point_created = res.created
            report.restore_point_reason = res.reason
            self.bus.publish("safety.restore_point", res)

        for planned in selected:
            rule = planned.rule
            try:
                outcome = rule.apply()
            except Exception as exc:
                log.exception("Rule %s apply crashed", rule.id)
                report.failed.append((rule.id, str(exc)))
                report.results.append(RuleApplyResult(
                    rule_id=rule.id, title=rule.title, status="failed",
                    detail=str(exc), admin_required=rule.requires_admin,
                ))
                continue

            if not outcome.ok:
                report.failed.append((rule.id, outcome.message))
                report.results.append(RuleApplyResult(
                    rule_id=rule.id, title=rule.title, status="failed",
                    detail=outcome.message, admin_required=rule.requires_admin,
                ))
                self.history.add(ActionRecord.new(
                    category="optimize",
                    action=rule.id,
                    summary=f"{rule.title} — {outcome.message}",
                    risk=rule.risk,
                    reversible=False,
                    status="failed",
                    payload={"reason": outcome.message},
                ))
                continue

            backup_id: Optional[str] = None
            if rule.reversible and outcome.backup_payload is not None:
                backup_id = self.backups.save(
                    kind=rule.id,
                    description=rule.title,
                    data=outcome.backup_payload,
                )

            # Post-apply verification: re-evaluate the rule. If it STILL says
            # "applicable", the change almost certainly didn't stick (common
            # symptom of running without admin rights on an HKLM rule).
            # Advisory rules are skipped — by definition they don't change state.
            verify_status = "applied"
            verify_detail = outcome.message
            if not rule.advisory:
                try:
                    re_eval = rule.evaluate(plan.hardware)
                    if re_eval.applicable:
                        # Change didn't take effect.
                        verify_status = "not_verified"
                        verify_detail = (
                            f"{outcome.message}\nPost-apply check: system still "
                            "reports this setting as not applied — "
                            + ("needs admin rights." if rule.requires_admin
                               else "the change may have been blocked by policy or AV.")
                        )
                except Exception:
                    log.debug("Post-apply verification crashed for %s", rule.id, exc_info=True)

            # HAGS and any other rule whose description mentions "reboot"
            # is expected to verify as still-applicable until the OS restarts.
            if verify_status == "not_verified" and (
                "reboot" in outcome.message.lower() or rule.id == "gpu.hw_scheduling"
            ):
                verify_status = "needs_reboot"
                verify_detail = f"{outcome.message}\nRestart Windows to activate."

            report.results.append(RuleApplyResult(
                rule_id=rule.id, title=rule.title, status=verify_status,
                detail=verify_detail, admin_required=rule.requires_admin,
            ))

            record = ActionRecord.new(
                category="optimize",
                action=rule.id,
                summary=f"{rule.title}: {outcome.message}",
                risk=rule.risk,
                reversible=bool(backup_id),
                status="applied" if verify_status == "applied" else verify_status,
                payload={"impact": rule.impact, "evidence": planned.evaluation.evidence},
                rollback_ref=backup_id,
            )
            self.history.add(record)
            report.applied.append(record)

        self.bus.publish("opt.plan_applied", report)
        return report

    # ------------------------------------------------------------------ register restorers
    def bind_rollback(self, rollback_engine) -> None:
        """Register every rule's restore function with a RollbackEngine."""
        for rule in self.rules:
            if rule.reversible:
                rollback_engine.register(rule.id, rule.restore)
