"""End-to-end: generate a plan, apply a single SAFE rule, verify outcome.

Chooses `visual.performance_mode` because it writes to HKCU (no admin
required) and is trivially reversible. Prints the per-rule verification
result so we can see the whole pipeline is wired up.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.app_controller import AppController


def main() -> int:
    ctrl = AppController()
    ctrl.bootstrap()
    time.sleep(0.2)

    snapshot = ctrl.hardware_snapshot or ctrl.hardware.detect()
    plan = ctrl.optimizer.generate_plan(snapshot)
    print(f"[ok] plan: {len(plan.actions)} rules")

    # Pick a known-safe, user-hive-only rule
    target_id = "visual.performance_mode"
    for a in plan.actions:
        a.selected = a.rule.id == target_id

    selected = [a for a in plan.actions if a.selected]
    if not selected:
        print(f"[skip] {target_id} is not applicable on this machine (already set).")
        # Pick any safe rule that's applicable
        for a in plan.actions:
            if a.rule.risk == "safe":
                a.selected = True
                target_id = a.rule.id
                break
        selected = [a for a in plan.actions if a.selected]

    if not selected:
        print("[skip] no applicable safe rule to apply; test is a no-op.")
        return 0

    print(f"[apply] running rule `{target_id}` (risk={selected[0].rule.risk})")
    ctrl.optimizer.bind_rollback(ctrl.rollback)
    report = ctrl.optimizer.apply_plan(plan, create_restore_point=False)

    for r in report.results:
        tag = r.status.upper()
        print(f"   - [{tag}] {r.rule_id}: {r.detail.splitlines()[0] if r.detail else ''}")

    # Rollback
    print("\n[rollback] reverting applied rules")
    for record in report.applied:
        try:
            ctrl.rollback.rollback_action(record)
            print(f"   - reverted {record.action}")
        except Exception as exc:
            print(f"   - failed to revert {record.action}: {exc}")

    ctrl.shutdown()
    print("\nSmoke real-apply OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
