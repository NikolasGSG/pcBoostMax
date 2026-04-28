"""argparse-driven command runner. Imports stay lazy so `--help` is fast."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Callable, List, Optional


# ---------------------------------------------------------------- top-level
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="GameBoost",
        description="GameBoost CLI — headless access to optimization + diagnostics.",
    )
    p.add_argument(
        "--cli", action="store_true",
        help="Run in command-line mode (skips the Qt GUI).",
    )
    p.add_argument(
        "--json", action="store_true",
        help="Emit JSON instead of human text where applicable.",
    )

    sub = p.add_subparsers(dest="command", metavar="<command>")

    # ---- optimize ----------------------------------------------------------
    s = sub.add_parser(
        "optimize",
        help="Generate (and optionally apply) an optimization plan.",
    )
    s.add_argument("--plan", choices=["balanced", "max-perf", "laptop", "absolute"],
                   default="balanced",
                   help="Which preset to use.")
    s.add_argument("--apply", action="store_true",
                   help="Actually apply changes (default: dry-run preview).")
    s.add_argument("--no-restore-point", action="store_true",
                   help="Skip creating a Windows restore point before applying.")

    # ---- diagnose ----------------------------------------------------------
    s = sub.add_parser(
        "diagnose",
        help="Run the auto-troubleshooter for a symptom.",
    )
    s.add_argument(
        "symptom",
        choices=["stutter", "low-fps", "latency", "slow-boot", "thermal", "freezes"],
    )

    # ---- inspect -----------------------------------------------------------
    s = sub.add_parser("inspect", help="Run a hardware inspector.")
    s.add_argument(
        "target",
        choices=["ram", "pcie", "ssd", "drivers", "all"],
    )

    # ---- bench -------------------------------------------------------------
    s = sub.add_parser("bench", help="Run network benchmarks.")
    s.add_argument("kind", choices=["dns", "ping", "boot"])

    # ---- memory ------------------------------------------------------------
    s = sub.add_parser("memory", help="Memory utilities.")
    s.add_argument("action", choices=["trim", "status"])

    # ---- rollback ----------------------------------------------------------
    s = sub.add_parser("rollback", help="Rollback applied changes.")
    s.add_argument("scope", choices=["last", "session", "all"], default="last", nargs="?")

    # ---- list-services -----------------------------------------------------
    s = sub.add_parser("services", help="Service tweaker.")
    s.add_argument("action", choices=["list", "recommendations", "apply", "restore"])

    return p


# ---------------------------------------------------------------- dispatcher
def run_cli(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    handler: Callable[[argparse.Namespace], int] = {
        "optimize": _cmd_optimize,
        "diagnose": _cmd_diagnose,
        "inspect": _cmd_inspect,
        "bench": _cmd_bench,
        "memory": _cmd_memory,
        "rollback": _cmd_rollback,
        "services": _cmd_services,
    }.get(args.command, _cmd_unknown)
    try:
        return handler(args)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130


def _emit(args: argparse.Namespace, payload, *, plain_text: str) -> None:
    if args.json:
        print(json.dumps(payload, default=str, indent=2))
    else:
        print(plain_text)


# ---------------------------------------------------------------- commands
def _cmd_optimize(args: argparse.Namespace) -> int:
    from ..core.app_controller import AppController

    ctrl = AppController()
    hardware = ctrl.hardware.detect()
    plan = ctrl.optimizer.generate_plan(hardware)

    payload = {
        "plan": args.plan,
        "expected_score": plan.expected_score,
        "actions": [
            {
                "id": a.rule.id,
                "title": a.rule.title,
                "category": a.rule.category,
                "selected": a.selected,
                "score": a.evaluation.score,
                "reason": a.evaluation.reason,
            }
            for a in plan.actions if a.evaluation.applicable
        ],
    }

    text_lines = [f"Plan: {args.plan}  (expected score {plan.expected_score})"]
    for a in payload["actions"]:
        text_lines.append(f"  [{a['category']:<10}] {a['title']}  (+{a['score']})")

    _emit(args, payload, plain_text="\n".join(text_lines))

    if not args.apply:
        if not args.json:
            print("\nDry-run only. Re-run with --apply to make changes.")
        return 0

    print("\nApplying...")
    report = ctrl.optimizer.apply_plan(plan, create_restore_point=not args.no_restore_point)
    if not args.json:
        print(f"Applied {len(report.applied)}, failed {len(report.failed)}, skipped {len(report.skipped)}.")
    return 0 if not report.failed else 1


def _cmd_diagnose(args: argparse.Namespace) -> int:
    from ..diagnostics import Symptom, Troubleshooter
    sym_map = {
        "stutter": Symptom.GAME_STUTTERS,
        "low-fps": Symptom.LOW_FPS,
        "latency": Symptom.HIGH_LATENCY,
        "slow-boot": Symptom.SLOW_BOOT,
        "thermal": Symptom.SYSTEM_HOT,
        "freezes": Symptom.RANDOM_FREEZES,
    }
    diag = Troubleshooter().diagnose(sym_map[args.symptom])

    text = [f"Diagnosis for: {args.symptom}", diag.summary, ""]
    text.append("Recommended steps:")
    for i, step in enumerate(diag.steps, 1):
        suffix = " (manual)" if step.manual else ""
        text.append(f"  {i}. [{step.confidence:>3}%] {step.title}{suffix}")
        if step.detail:
            text.append(f"       {step.detail}")
    if diag.findings:
        text.append("")
        text.append("Hardware findings:")
        for f in diag.findings:
            text.append(f"  - [{f.severity.value}] {f.title}")

    payload = {
        "symptom": args.symptom,
        "summary": diag.summary,
        "steps": [s.__dict__ for s in diag.steps],
        "findings": [
            {"id": f.id, "severity": f.severity.value, "title": f.title}
            for f in diag.findings
        ],
    }
    _emit(args, payload, plain_text="\n".join(text))
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    from ..system.inspectors import (
        DriverAuditor, NvmeHealthInspector, PcieLinkInspector, RamXmpInspector,
    )
    targets = {"ram": RamXmpInspector, "pcie": PcieLinkInspector,
               "ssd": NvmeHealthInspector, "drivers": DriverAuditor}
    if args.target == "all":
        kinds = list(targets.keys())
    else:
        kinds = [args.target]

    all_findings = []
    for kind in kinds:
        cls = targets[kind]
        inspector = cls()
        findings = inspector.inspect()
        all_findings.append({"target": kind, "findings": [
            {"id": f.id, "severity": f.severity.value, "title": f.title, "detail": f.detail}
            for f in findings
        ]})

    text = []
    for block in all_findings:
        text.append(f"-- {block['target'].upper()} --")
        if not block["findings"]:
            text.append("  No findings.")
        else:
            for f in block["findings"]:
                text.append(f"  [{f['severity']}] {f['title']}")
                if f["detail"]:
                    text.append(f"     {f['detail']}")
        text.append("")
    _emit(args, all_findings, plain_text="\n".join(text))
    return 0


def _cmd_bench(args: argparse.Namespace) -> int:
    if args.kind == "dns":
        from ..monitoring.network import DnsBenchmark
        results = DnsBenchmark().run()
        payload = [
            {
                "label": r.label, "server": r.server,
                "mean_ms": round(r.mean_ms, 2), "losses": r.losses,
                "is_current": r.is_current,
            }
            for r in results
        ]
        text = ["DNS benchmark (lower is better):"]
        for r in results:
            cur = " *current*" if r.is_current else ""
            if r.reachable:
                text.append(f"  {r.label:<32}  {r.mean_ms:>6.1f} ms (loss {r.losses}){cur}")
            else:
                text.append(f"  {r.label:<32}  unreachable{cur}")
        _emit(args, payload, plain_text="\n".join(text))
        return 0
    if args.kind == "ping":
        from ..monitoring.network import PingTester
        results = PingTester().run()
        payload = [
            {
                "label": r.target.label, "host": r.target.host,
                "mean_ms": round(r.mean_ms, 2), "jitter_ms": round(r.jitter_ms, 2),
                "losses": r.losses, "quality": r.quality_band(),
            }
            for r in results
        ]
        text = ["Game-server ping test:"]
        for r in results:
            if r.reachable:
                text.append(f"  {r.target.label:<32}  {r.mean_ms:>6.1f} ms  ({r.quality_band()})")
            else:
                text.append(f"  {r.target.label:<32}  unreachable")
        _emit(args, payload, plain_text="\n".join(text))
        return 0
    if args.kind == "boot":
        from ..monitoring.boot_time import BootTimeService
        svc = BootTimeService()
        try:
            r = svc.benchmark()
        except Exception as exc:
            print(f"Boot benchmark failed: {exc}", file=sys.stderr)
            return 1
        text = [
            f"Boot time benchmark:",
            f"  Total:    {r.total_ms / 1000:.1f} s",
            f"  Kernel:   {r.kernel_ms / 1000:.1f} s",
            f"  Login:    {r.login_ms / 1000:.1f} s",
            f"  Startup:  {r.startup_ms / 1000:.1f} s",
        ]
        _emit(args, r.__dict__, plain_text="\n".join(text))
        return 0
    return 1


def _cmd_memory(args: argparse.Namespace) -> int:
    import psutil
    if args.action == "status":
        vm = psutil.virtual_memory()
        info = {
            "total_mb": vm.total / (1024 * 1024),
            "available_mb": vm.available / (1024 * 1024),
            "used_mb": vm.used / (1024 * 1024),
            "percent": vm.percent,
        }
        text = (
            f"RAM total:     {info['total_mb']:.0f} MB\n"
            f"RAM used:      {info['used_mb']:.0f} MB ({info['percent']:.1f}%)\n"
            f"Available:     {info['available_mb']:.0f} MB"
        )
        _emit(args, info, plain_text=text)
        return 0

    # trim
    from ..core.event_bus import EventBus
    from ..system.memory_trim import MemoryTrimService
    svc = MemoryTrimService(EventBus())
    result = svc.trim()
    text = (
        f"Trimmed {result.freed_mb:.0f} MB from {result.trimmed_processes} processes "
        f"in {result.elapsed_ms:.0f} ms (standby purged: {result.standby_purged})."
    )
    _emit(args, result.__dict__, plain_text=text)
    return 0


def _cmd_rollback(args: argparse.Namespace) -> int:
    from ..core.app_controller import AppController
    ctrl = AppController()
    # Make sure rule restorers are bound before we try to roll anything back.
    ctrl.optimizer.bind_rollback(ctrl.rollback)
    history = ctrl.history.all()
    if not history:
        print("Nothing to rollback.")
        return 0
    if args.scope == "last":
        rec = history[-1]
        ok = ctrl.rollback.rollback_action(rec)
        print(f"Rolled back '{rec.summary}': {'ok' if ok else 'failed'}")
        return 0 if ok else 1
    if args.scope == "session":
        import time as _t
        cutoff = _t.time() - 12 * 3600
        targets = [r for r in history if r.ts >= cutoff and r.reversible]
        for rec in reversed(targets):
            ctrl.rollback.rollback_action(rec)
        print(f"Reversed {len(targets)} session actions.")
        return 0
    # all
    targets = [r for r in history if r.reversible]
    for rec in reversed(targets):
        ctrl.rollback.rollback_action(rec)
    print(f"Reversed {len(targets)} reversible actions.")
    return 0


def _cmd_services(args: argparse.Namespace) -> int:
    from ..optimization.service_tweaker import ServiceTweaker
    svc = ServiceTweaker()
    if args.action == "list":
        states = svc.list_states()
        payload = [s.__dict__ for s in states]
        text = ["Service catalogue (curated):"]
        for s in states:
            text.append(f"  {s.name:<24} {s.start_type:<10} {s.state:<10}  -> {s.recommendation}")
        _emit(args, payload, plain_text="\n".join(text))
        return 0
    if args.action == "recommendations":
        recs = svc.recommendations()
        payload = [r.__dict__ for r in recs]
        text = ["Recommended changes:"]
        for r in recs:
            text.append(f"  {r.name:<24} {r.start_type:<10} -> {r.recommendation}")
        if not recs:
            text.append("  (nothing to change — already optimal)")
        _emit(args, payload, plain_text="\n".join(text))
        return 0
    if args.action == "apply":
        report, payload = svc.apply_recommendations()
        text = f"Changed {len(report.changed)} services. Failed {len(report.failed)}."
        _emit(args, {"report": [c.__dict__ for c in report.changed], "backup": payload},
              plain_text=text)
        return 0 if not report.failed else 1
    if args.action == "restore":
        # We don't have the backup in the CLI flow — push the user to GUI.
        print("Service restore requires the GUI history. Open GameBoost -> Settings -> Restore.")
        return 0
    return 1


def _cmd_unknown(_args: argparse.Namespace) -> int:
    print("Unknown command.", file=sys.stderr)
    return 2
