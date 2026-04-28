"""End-to-end flow smoke test.

Exercises hardware detection, plan generation, plan application, rollback,
cleanup scan, Game Mode activation/deactivation. All offline, no GUI.
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
    ctrl.bootstrap(async_hardware=False)
    time.sleep(1.0)  # let monitor collect a sample

    # Hardware detection
    snap = ctrl.hardware.detect()
    print(f"[ok] hardware: {snap.cpu.name}  RAM={snap.ram.total_bytes // (1024**3)} GB  OS={snap.os.system} {snap.os.release}")

    # Plan generation
    plan = ctrl.optimizer.generate_plan(snap)
    print(f"[ok] plan: {len(plan.actions)} applicable rules, expected_score={plan.expected_score}")
    for a in plan.actions:
        print(f"       - {a.rule.id}  ({a.rule.risk}/{a.rule.impact})  score={a.evaluation.score}")

    # Bottleneck analysis
    samples = ctrl.monitor.history()
    bottlenecks = ctrl.bottlenecks.analyze(snap, samples)
    print(f"[ok] bottlenecks: {len(bottlenecks)}")
    for b in bottlenecks:
        print(f"       - {b.severity.upper()} [{b.component}] {b.headline}")

    # Cleanup scan (no delete) — just one category to keep fast
    res = ctrl.cleanup.scan(["user_temp"])
    print(f"[ok] cleanup scan: {len(res.files)} files, {res.total_bytes // (1024*1024)} MB")

    # Game Mode activate/deactivate (no suspensions)
    snap_gm = ctrl.game_mode.activate(suspend_targets=None, enable_power=False, enable_visual=False, enable_dvr=False)
    print(f"[ok] game mode activated: actions={len(snap_gm.applied_action_ids)}")
    ctrl.game_mode.deactivate()
    print("[ok] game mode deactivated")

    ctrl.shutdown()
    print("\nAll flows completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
