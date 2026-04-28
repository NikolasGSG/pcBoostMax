"""Per-game profiles — settings that get applied while a game is running.

Each :class:`GameProfile` describes how the system should be tuned for one
specific title. When the foreground process matches the profile's
``exe_match`` (or the user manually presses "Optimize" on a tile), the
profile is applied; when the game closes, the original baseline is
restored.

The profile model intentionally keeps the *what* small and reversible:

* **power_plan** — switch to Ultimate / High Performance, restore on exit.
* **process_priority** — set the game process to AboveNormal / High.
* **process_affinity** — pin to a CPU mask (None = all cores).
* **suspend_processes** — list of process names to ``psutil.suspend()`` for
  the duration of the game session, then resume.
* **fps_cap_hz** — soft FPS cap (informational; surfaced in HUD).
* **disable_gamebar** — toggles Xbox Game Bar key off for this session.

Every profile load/apply path is wrapped in try/except so a single broken
profile can never crash the app.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Iterable, List, Optional

from ..utils.logger import get_logger
from ..utils.paths import APP_DATA_DIR

if TYPE_CHECKING:
    from ..core.app_controller import AppController

log = get_logger("games.profiles")


_PROFILE_DIR = APP_DATA_DIR / "game_profiles"


@dataclass
class GameProfile:
    """Per-game tuning record."""

    game_id: str                                      # matches Game.id
    name: str                                         # game name (for UI)
    exe_match: List[str] = field(default_factory=list)
    power_plan: str = "ultimate"                      # "ultimate" | "high" | "balanced" | "off"
    process_priority: str = "above_normal"            # "normal" | "above_normal" | "high" | "realtime" | "off"
    process_affinity_mask: Optional[int] = None       # CPU mask, None = all
    suspend_processes: List[str] = field(default_factory=list)
    fps_cap_hz: int = 0                               # 0 = uncapped
    disable_gamebar: bool = True
    enabled: bool = True
    last_applied_ts: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "GameProfile":
        return cls(**{k: v for k, v in d.items() if k in {f.name for f in cls.__dataclass_fields__.values()}})

    @classmethod
    def default_for(cls, game_id: str, name: str, exe_path: str = "") -> "GameProfile":
        """Sensible default — works as a 'no decisions needed' baseline."""
        exe_name = Path(exe_path).name if exe_path else ""
        return cls(
            game_id=game_id,
            name=name,
            exe_match=[exe_name] if exe_name else [],
        )


class _ProfileApplyState:
    """Tracks one currently-applied profile so we can restore baseline."""

    def __init__(self) -> None:
        self.profile: Optional[GameProfile] = None
        self.previous_power_plan: Optional[str] = None
        self.suspended_pids: list[int] = []
        self.applied_at: float = 0.0


class GameProfileService:
    """Public API for per-game profile load / apply / restore.

    The service is a singleton attached to the AppController so the
    AutoPilot module and the Game Hub view share state.
    """

    _SINGLETON: "GameProfileService | None" = None

    @classmethod
    def get(cls, controller: "AppController") -> "GameProfileService":
        if cls._SINGLETON is None:
            cls._SINGLETON = cls(controller)
        return cls._SINGLETON

    def __init__(self, controller: "AppController") -> None:
        self._ctrl = controller
        self._profiles: dict[str, GameProfile] = {}
        self._state = _ProfileApplyState()
        self._lock = Lock()
        _PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self._load_all()

    # ------------------------------------------------------------------ load/save
    def _load_all(self) -> None:
        for f in _PROFILE_DIR.glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                p = GameProfile.from_dict(d)
                self._profiles[p.game_id] = p
            except Exception:
                log.warning("Skipping unreadable profile %s", f.name)

    def save(self, profile: GameProfile) -> None:
        with self._lock:
            self._profiles[profile.game_id] = profile
            try:
                safe_id = profile.game_id.replace(":", "_").replace("/", "_")
                (_PROFILE_DIR / f"{safe_id}.json").write_text(
                    json.dumps(profile.to_dict(), indent=2),
                    encoding="utf-8",
                )
            except Exception:
                log.exception("Failed to save profile for %s", profile.game_id)

    def get_for_id(self, game_id: str) -> Optional[GameProfile]:
        return self._profiles.get(game_id)

    def all(self) -> List[GameProfile]:
        return list(self._profiles.values())

    # ------------------------------------------------------------------ matching
    def match(self, *, name: str = "", exe: str = "") -> Optional[GameProfile]:
        """Find a profile by exe basename or game name (case-insensitive)."""
        exe_basename = Path(exe).name.lower() if exe else ""
        nl = (name or "").strip().lower()
        for p in self._profiles.values():
            if not p.enabled:
                continue
            if exe_basename and exe_basename in {e.lower() for e in p.exe_match if e}:
                return p
            if nl and nl == p.name.lower():
                return p
        return None

    # ------------------------------------------------------------------ apply
    def apply_for(self, *, name: str = "", exe: str = "") -> bool:
        """Apply the matching profile for a foreground game. Returns True
        if a profile was applied."""
        p = self.match(name=name, exe=exe)
        if not p:
            return False
        return self.apply(p, exe=exe)

    def apply(self, profile: GameProfile, *, exe: str = "") -> bool:
        with self._lock:
            if self._state.profile is not None:
                # Already running another profile — restore first.
                self._restore_locked()
            try:
                self._apply_locked(profile, exe=exe)
                self._state.profile = profile
                self._state.applied_at = time.time()
                profile.last_applied_ts = self._state.applied_at
                self.save(profile)
                self._ctrl.bus.publish("game_profile.applied", profile)
                return True
            except Exception:
                log.exception("Profile apply failed")
                return False

    def restore_baseline(self) -> None:
        with self._lock:
            self._restore_locked()

    # ------------------------------------------------------------------ internal
    def _apply_locked(self, profile: GameProfile, *, exe: str = "") -> None:
        # 1. Power plan ------------------------------------------------------
        if profile.power_plan and profile.power_plan != "off":
            try:
                from ..optimization.rules.power_plan_rule import PowerPlanService
                svc = PowerPlanService()
                self._state.previous_power_plan = svc.active_plan_guid()
                target_guid = svc.guid_for_alias(profile.power_plan)
                if target_guid and target_guid != self._state.previous_power_plan:
                    svc.activate(target_guid)
                    log.info("Profile %s: switched power plan -> %s",
                             profile.name, profile.power_plan)
            except Exception:
                log.exception("Profile power-plan switch failed")

        # 2. Process priority + affinity ------------------------------------
        if exe:
            try:
                self._set_priority_and_affinity(exe, profile)
            except Exception:
                log.exception("Profile priority/affinity set failed")

        # 3. Suspend background processes -----------------------------------
        if profile.suspend_processes:
            self._state.suspended_pids = self._suspend_matching(profile.suspend_processes)

    def _restore_locked(self) -> None:
        if not self._state.profile:
            return
        # Restore power plan
        try:
            if self._state.previous_power_plan:
                from ..optimization.rules.power_plan_rule import PowerPlanService
                PowerPlanService().activate(self._state.previous_power_plan)
        except Exception:
            log.exception("Profile power-plan restore failed")
        # Resume suspended processes
        for pid in self._state.suspended_pids:
            try:
                import psutil
                proc = psutil.Process(pid)
                proc.resume()
            except Exception:
                pass
        old = self._state.profile
        self._state = _ProfileApplyState()
        self._ctrl.bus.publish("game_profile.restored", old)

    # ------------------------------------------------------------------ helpers
    def _set_priority_and_affinity(self, exe: str, profile: GameProfile) -> None:
        """Find the running process matching ``exe`` and set its priority + affinity."""
        import psutil
        target = Path(exe).name.lower() if exe else ""
        if not target:
            return
        priority_map = {
            "normal":       psutil.NORMAL_PRIORITY_CLASS,
            "above_normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS,
            "high":         psutil.HIGH_PRIORITY_CLASS,
            "realtime":     psutil.REALTIME_PRIORITY_CLASS,
        }
        prio = priority_map.get(profile.process_priority)
        for proc in psutil.process_iter(attrs=["name", "pid"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name != target:
                    continue
                if prio is not None and profile.process_priority != "off":
                    proc.nice(prio)
                if profile.process_affinity_mask is not None:
                    cores = [i for i in range(psutil.cpu_count() or 0)
                             if profile.process_affinity_mask & (1 << i)]
                    if cores:
                        proc.cpu_affinity(cores)
            except Exception:
                continue

    def _suspend_matching(self, names: Iterable[str]) -> list[int]:
        suspended: list[int] = []
        try:
            import psutil
            wanted = {n.lower() for n in names if n}
            for proc in psutil.process_iter(attrs=["name", "pid"]):
                try:
                    n = (proc.info.get("name") or "").lower()
                    if n in wanted:
                        proc.suspend()
                        suspended.append(int(proc.info["pid"]))
                except Exception:
                    continue
        except Exception:
            log.exception("Process suspend pass failed")
        return suspended
