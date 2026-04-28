"""ViewModel for the Optimize view."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from ...core.app_controller import AppController
from ...optimization.optimization_engine import ApplyReport, OptimizationPlan
from ...system.hardware_detector import HardwareSnapshot
from ...utils.logger import get_logger
from .base import ViewModel

log = get_logger("ui.optimize_vm")


class OptimizeViewModel(ViewModel):
    plan_ready = pyqtSignal(object)       # OptimizationPlan
    plan_applied = pyqtSignal(object)     # ApplyReport
    plan_refreshed = pyqtSignal(object)   # OptimizationPlan (no heavy rebuild)

    def __init__(self, controller: AppController, parent: QObject | None = None) -> None:
        super().__init__(controller, parent)
        self._plan: Optional[OptimizationPlan] = None
        controller.bus.subscribe("opt.plan_ready", self.plan_ready.emit)
        controller.bus.subscribe("opt.plan_applied", self.plan_applied.emit)
        controller.bus.subscribe("opt.state_changed", self._on_state_changed)

    # ------------------------------------------------------------------ state
    @property
    def is_admin(self) -> bool:
        return self.controller.is_admin

    # ------------------------------------------------------------------ actions
    def regenerate(self) -> Optional[OptimizationPlan]:
        snapshot: HardwareSnapshot | None = self.controller.hardware_snapshot
        if snapshot is None:
            snapshot = self.controller.hardware.detect()
        return self.controller.optimizer.generate_plan(snapshot)

    def refresh_plan(self, plan: OptimizationPlan) -> OptimizationPlan:
        """Re-evaluate applicability of each rule without regenerating."""
        for action in plan.actions:
            try:
                action.evaluation = action.rule.evaluate(plan.hardware)
            except Exception:
                # A single broken rule must not take down the whole refresh.
                log.exception("rule re-eval crashed: %s", action.rule.id)
        self.plan_refreshed.emit(plan)
        return plan

    def apply(self, plan: OptimizationPlan, *, create_restore_point: Optional[bool] = None) -> ApplyReport:
        # Make sure rollback is wired for the rules in this plan.
        self.controller.optimizer.bind_rollback(self.controller.rollback)
        report = self.controller.optimizer.apply_plan(plan, create_restore_point=create_restore_point)
        # Emit state-changed so listeners (including this VM) know to re-check
        self.controller.bus.publish("opt.state_changed", {"reason": "apply"})
        return report

    # ------------------------------------------------------------------ internals
    def _on_state_changed(self, _payload: dict | None = None) -> None:
        # When system state changes (apply/rollback), re-check the current
        # plan applicability so "APPLIED" badges stay in sync.
        if self._plan is not None:
            self.refresh_plan(self._plan)

    @property
    def current_plan(self) -> OptimizationPlan | None:
        return self._plan

    @current_plan.setter
    def current_plan(self, value: OptimizationPlan | None) -> None:
        self._plan = value
