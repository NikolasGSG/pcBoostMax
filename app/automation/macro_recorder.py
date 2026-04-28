"""Macro library — chained actions with one-click playback.

A macro is a list of :class:`MacroAction` records. Each action has a
``kind`` ("apply_rule", "memory_trim", "tame_background_apps",
"set_theme", "wait", "press_to_boost") and a small payload.

The :class:`MacroRunner` knows how to execute each kind; it plugs into
the existing services (:class:`OptimizationEngine`,
:class:`MemoryTrimService`, :class:`BoostBurstService`,
:class:`BackgroundAppTamer`). Failures are reported per-action so a
partial run isn't lost.

The library is persisted to ``logs/macros.json`` (alongside other user
state) and ships with three built-in macros so the feature is useful
on day one.
"""
from __future__ import annotations

import enum
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..utils.logger import get_logger
from ..utils.paths import MACROS_DIR, ensure_app_dirs

log = get_logger("automation.macro")


_FILENAME = "macros.json"


# ---------------------------------------------------------------- model
class MacroKind(str, enum.Enum):
    APPLY_RULE = "apply_rule"
    MEMORY_TRIM = "memory_trim"
    TAME_APPS = "tame_background_apps"
    SET_THEME = "set_theme"
    PRESS_TO_BOOST = "press_to_boost"
    WAIT = "wait"


@dataclass
class MacroAction:
    kind: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Macro:
    id: str
    name: str
    description: str = ""
    actions: List[MacroAction] = field(default_factory=list)
    icon: str = ""

    @classmethod
    def new(cls, name: str, *, description: str = "") -> "Macro":
        return cls(id=str(uuid.uuid4())[:8], name=name, description=description)


@dataclass
class MacroStepResult:
    kind: str
    ok: bool
    detail: str = ""


@dataclass
class MacroRunResult:
    macro_id: str
    name: str
    started_at: float
    elapsed_s: float
    steps: List[MacroStepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.steps)


# ---------------------------------------------------------------- defaults
DEFAULT_MACROS: List[Macro] = [
    Macro(
        id="macro_pre_match",
        name="Pre-Match Sweep",
        description="Memory trim + tame background apps + 30-min boost burst.",
        icon="🎯",
        actions=[
            MacroAction(MacroKind.TAME_APPS.value, {"only_safe": True}),
            MacroAction(MacroKind.MEMORY_TRIM.value, {"purge_standby": True}),
            MacroAction(MacroKind.PRESS_TO_BOOST.value, {"duration_s": 1800}),
        ],
    ),
    Macro(
        id="macro_workday",
        name="Workday Mode",
        description="Restore lowered processes + neutral theme + memory trim.",
        icon="💼",
        actions=[
            MacroAction(MacroKind.SET_THEME.value, {"preset": "stealth_mono"}),
            MacroAction(MacroKind.MEMORY_TRIM.value, {"purge_standby": False}),
        ],
    ),
    Macro(
        id="macro_late_night",
        name="Late-Night Low-Latency",
        description="Network optimizations + memory trim + cyber pink theme.",
        icon="🌙",
        actions=[
            MacroAction(MacroKind.APPLY_RULE.value, {"rule_id": "network.nagle_off"}),
            MacroAction(MacroKind.APPLY_RULE.value, {"rule_id": "system.mmcss_responsiveness"}),
            MacroAction(MacroKind.MEMORY_TRIM.value, {"purge_standby": True}),
            MacroAction(MacroKind.SET_THEME.value, {"preset": "cyber_pink"}),
        ],
    ),
]


def _clone_default(m: Macro) -> Macro:
    """Deep-copy a default macro, preserving MacroAction instances."""
    return Macro(
        id=m.id,
        name=m.name,
        description=m.description,
        icon=m.icon,
        actions=[MacroAction(a.kind, dict(a.params)) for a in m.actions],
    )


# ============================================================================
# Library — load / save / mutate
# ============================================================================
class MacroLibrary:
    """Persisted user-editable list of macros."""

    def __init__(self, *, path: Optional[Path] = None) -> None:
        ensure_app_dirs()
        self._path = path or (MACROS_DIR / _FILENAME)
        self._macros: List[Macro] = []
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def all(self) -> List[Macro]:
        return list(self._macros)

    def by_id(self, macro_id: str) -> Optional[Macro]:
        return next((m for m in self._macros if m.id == macro_id), None)

    def add(self, macro: Macro) -> None:
        self._macros.append(macro)
        self._save()

    def update(self, macro: Macro) -> None:
        for i, m in enumerate(self._macros):
            if m.id == macro.id:
                self._macros[i] = macro
                break
        else:
            self._macros.append(macro)
        self._save()

    def delete(self, macro_id: str) -> None:
        self._macros = [m for m in self._macros if m.id != macro_id]
        self._save()

    def reset_to_defaults(self) -> None:
        self._macros = [_clone_default(m) for m in DEFAULT_MACROS]
        self._save()

    # ------------------------------------------------------------------ io
    def _load(self) -> None:
        if not self._path.exists():
            self._macros = [_clone_default(m) for m in DEFAULT_MACROS]
            self._save()
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._macros = [
                Macro(
                    id=m["id"],
                    name=m["name"],
                    description=m.get("description", ""),
                    icon=m.get("icon", ""),
                    actions=[MacroAction(a["kind"], a.get("params", {})) for a in m.get("actions", [])],
                )
                for m in data.get("macros", [])
            ]
            if not self._macros:
                self._macros = [_clone_default(m) for m in DEFAULT_MACROS]
                self._save()
        except Exception:
            log.exception("macros.json unreadable; resetting to defaults")
            self._macros = [_clone_default(m) for m in DEFAULT_MACROS]
            self._save()

    def _save(self) -> None:
        try:
            payload = {"macros": [
                {
                    "id": m.id,
                    "name": m.name,
                    "description": m.description,
                    "icon": m.icon,
                    "actions": [{"kind": a.kind, "params": a.params} for a in m.actions],
                }
                for m in self._macros
            ]}
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            log.exception("macros save failed")


# ============================================================================
# Runner — applies a macro to the live services
# ============================================================================
class MacroRunner:
    """Execute a Macro against injected services.

    Service references are optional; an unknown / unavailable service
    just logs a 'skipped' step rather than crashing the whole macro.
    """

    def __init__(
        self,
        *,
        optimization_engine=None,         # OptimizationEngine
        memory_service=None,              # MemoryTrimService
        boost_service=None,               # BoostBurstService
        tamer=None,                       # BackgroundAppTamer
        theme_setter: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._opt = optimization_engine
        self._mem = memory_service
        self._boost = boost_service
        self._tamer = tamer
        self._theme_setter = theme_setter

    def run(self, macro: Macro) -> MacroRunResult:
        started = time.time()
        result = MacroRunResult(macro_id=macro.id, name=macro.name,
                                started_at=started, elapsed_s=0.0)
        for action in macro.actions:
            step = self._run_action(action)
            result.steps.append(step)
        result.elapsed_s = time.time() - started
        return result

    # ------------------------------------------------------------------ dispatch
    def _run_action(self, action: MacroAction) -> MacroStepResult:
        try:
            if action.kind == MacroKind.APPLY_RULE.value:
                return self._apply_rule(action.params)
            if action.kind == MacroKind.MEMORY_TRIM.value:
                return self._memory_trim(action.params)
            if action.kind == MacroKind.TAME_APPS.value:
                return self._tame_apps(action.params)
            if action.kind == MacroKind.SET_THEME.value:
                return self._set_theme(action.params)
            if action.kind == MacroKind.PRESS_TO_BOOST.value:
                return self._press_to_boost(action.params)
            if action.kind == MacroKind.WAIT.value:
                return self._wait(action.params)
        except Exception as exc:
            log.exception("macro action %s failed", action.kind)
            return MacroStepResult(kind=action.kind, ok=False, detail=str(exc))
        return MacroStepResult(kind=action.kind, ok=False, detail="unknown action")

    # ------------------------------------------------------------------ kinds
    def _apply_rule(self, params: Dict[str, Any]) -> MacroStepResult:
        rule_id = params.get("rule_id")
        if not rule_id:
            return MacroStepResult(MacroKind.APPLY_RULE.value, False, "missing rule_id")
        if self._opt is None:
            return MacroStepResult(MacroKind.APPLY_RULE.value, False, "optimization engine not available")
        rule = next((r for r in self._opt.rules if r.id == rule_id), None)
        if rule is None:
            return MacroStepResult(MacroKind.APPLY_RULE.value, False, f"unknown rule {rule_id}")
        try:
            outcome = rule.apply()
        except Exception as exc:
            return MacroStepResult(MacroKind.APPLY_RULE.value, False, f"apply failed: {exc}")
        return MacroStepResult(
            MacroKind.APPLY_RULE.value, outcome.success,
            f"{rule.title}: {outcome.message}",
        )

    def _memory_trim(self, params: Dict[str, Any]) -> MacroStepResult:
        if self._mem is None:
            return MacroStepResult(MacroKind.MEMORY_TRIM.value, False, "memory service not available")
        purge = bool(params.get("purge_standby", True))
        result = self._mem.trim(purge_standby=purge)
        return MacroStepResult(
            MacroKind.MEMORY_TRIM.value, True,
            f"freed {result.freed_mb:.0f} MB from {result.trimmed_processes} procs",
        )

    def _tame_apps(self, params: Dict[str, Any]) -> MacroStepResult:
        if self._tamer is None:
            return MacroStepResult(MacroKind.TAME_APPS.value, False, "tamer not available")
        only_safe = bool(params.get("only_safe", True))
        candidates = self._tamer.candidates()
        tamed = 0
        for c in candidates:
            if only_safe and c.rule.safety != "safe":
                continue
            if self._tamer.tame(c):
                tamed += 1
        return MacroStepResult(
            MacroKind.TAME_APPS.value, True, f"tamed {tamed} background apps",
        )

    def _set_theme(self, params: Dict[str, Any]) -> MacroStepResult:
        preset = params.get("preset")
        if not preset:
            return MacroStepResult(MacroKind.SET_THEME.value, False, "missing preset")
        if self._theme_setter is None:
            return MacroStepResult(MacroKind.SET_THEME.value, False, "theme setter not wired")
        self._theme_setter(preset)
        return MacroStepResult(MacroKind.SET_THEME.value, True, f"theme → {preset}")

    def _press_to_boost(self, params: Dict[str, Any]) -> MacroStepResult:
        if self._boost is None:
            return MacroStepResult(MacroKind.PRESS_TO_BOOST.value, False, "boost service not available")
        duration = int(params.get("duration_s", 1800))
        try:
            self._boost.start(duration_s=duration)
        except Exception as exc:
            return MacroStepResult(MacroKind.PRESS_TO_BOOST.value, False, f"boost start failed: {exc}")
        return MacroStepResult(
            MacroKind.PRESS_TO_BOOST.value, True, f"boost burst started for {duration // 60} min",
        )

    def _wait(self, params: Dict[str, Any]) -> MacroStepResult:
        sec = float(params.get("seconds", 0))
        time.sleep(max(0.0, min(sec, 30.0)))   # cap at 30 s — macros should be fast
        return MacroStepResult(MacroKind.WAIT.value, True, f"waited {sec:.1f}s")
