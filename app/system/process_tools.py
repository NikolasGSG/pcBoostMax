"""Process introspection + management tools.

Two consumer-facing features:

* :class:`ProcessHunter` — enumerates running processes with CPU /
  RAM / disk / network signals, scores each one, and recommends actions
  (suspend / lower priority / kill) with explanations.

* :class:`BackgroundAppTamer` — a curated list of "definitely safe to
  kill while gaming" apps (Spotify helper renderers, OneDrive sync,
  Adobe CC daemon, etc.). Acts on the user's go-ahead.

Everything is reversible — we keep a list of suspended PIDs / lowered-
priority PIDs so a single "Restore" call puts them back.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import psutil

from ..safety.action_history import ActionHistory, ActionRecord
from ..utils.logger import get_logger

log = get_logger("system.process_tools")


# ---------------------------------------------------------------- reference
# Names of processes we never recommend touching.
PROTECTED_NAMES = {
    "system idle process", "system", "registry", "memory compression",
    "smss.exe", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe",
    "winlogon.exe", "fontdrvhost.exe", "dwm.exe", "explorer.exe",
    "svchost.exe", "msmpeng.exe", "securityhealthservice.exe",
    "audiodg.exe",
    "gameboostapex.exe",       # don't suicide
    "python.exe", "pythonw.exe",
    "powershell.exe",
}

# Curated apps we know users typically want quiet during a game session.
# Keys are lowercase exe names. Values include a short reason + a
# "preferred" remediation (suspend vs kill).
_BACKGROUND_TAMERS: Dict[str, "TamerRule"] = {}


@dataclass(frozen=True)
class TamerRule:
    name: str             # exe name, lowercase
    label: str            # human display name
    reason: str           # one-paragraph why
    preferred_action: str = "suspend"   # "suspend" | "lower_priority" | "kill"
    safety: str = "safe"  # "safe" | "review"


def _register(rule: TamerRule) -> None:
    _BACKGROUND_TAMERS[rule.name] = rule


for r in [
    TamerRule("onedrive.exe",        "OneDrive",          "Cloud sync — heavy network + disk while gaming.", "kill"),
    TamerRule("dropbox.exe",         "Dropbox",           "Cloud sync.", "kill"),
    TamerRule("googledrivesync.exe", "Google Drive",      "Cloud sync.", "kill"),
    TamerRule("creative cloud.exe",  "Adobe Creative Cloud", "Background updater.", "kill"),
    TamerRule("ccxprocess.exe",      "Adobe CCX Process", "Adobe Creative Cloud helper.", "kill"),
    TamerRule("acrobat.exe",         "Adobe Acrobat",     "Random PDF preview process.", "kill"),
    TamerRule("teams.exe",           "Microsoft Teams",   "RAM-heavy chat client.", "suspend"),
    TamerRule("slack.exe",           "Slack",             "Heavy Electron client.", "suspend"),
    TamerRule("discord.exe",         "Discord",           "Lower priority while gaming.", "lower_priority", "review"),
    TamerRule("spotify.exe",         "Spotify",           "Lower priority while gaming.", "lower_priority", "review"),
    TamerRule("chrome.exe",          "Chrome (helper renderers)", "Browser renderers eating RAM.", "lower_priority", "review"),
    TamerRule("msedge.exe",          "Edge (helpers)",    "Browser helpers eating RAM.", "lower_priority", "review"),
    TamerRule("firefox.exe",         "Firefox",           "Browser helpers eating RAM.", "lower_priority", "review"),
    TamerRule("razerservice.exe",    "Razer Synapse Service", "Razer background updater.", "suspend"),
    TamerRule("logioptionsplus_agent.exe", "Logi Options+ Agent", "Logitech device daemon.", "suspend"),
    TamerRule("nvidia web helper.exe",   "NVIDIA Web Helper", "NVIDIA telemetry helper.", "suspend"),
    TamerRule("nvcontainer.exe",     "NVIDIA Container",  "NVIDIA Container — leave running unless RTX HDR/Filters off.", "lower_priority", "review"),
]:
    _register(r)


# ============================================================================
# Process Hunter
# ============================================================================
@dataclass
class ProcessSummary:
    pid: int
    name: str
    cpu_percent: float
    ram_mb: float
    network_connections: int
    is_protected: bool
    is_self: bool
    suggestion: str = ""               # "suspend" | "lower_priority" | "kill" | ""
    suggestion_reason: str = ""
    started_at: float = 0.0


class ProcessHunter:
    """Enumerate + score processes."""

    SELF_PIDS: Set[int] = {0}    # filled in __init__ with our own pid

    def __init__(self) -> None:
        try:
            ProcessHunter.SELF_PIDS = {0, psutil.Process().pid}
        except Exception:
            ProcessHunter.SELF_PIDS = {0}

    def snapshot(self, *, sample_interval: float = 0.3) -> List[ProcessSummary]:
        """Return a sorted (highest impact first) list of processes."""
        # Prime CPU% counters
        for p in psutil.process_iter():
            try:
                p.cpu_percent(None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        time.sleep(sample_interval)

        # Collect connections in one pass — cheaper than asking per-pid.
        conns_by_pid: Dict[int, int] = {}
        try:
            for c in psutil.net_connections(kind="inet"):
                if c.pid is None:
                    continue
                conns_by_pid[c.pid] = conns_by_pid.get(c.pid, 0) + 1
        except (psutil.AccessDenied, OSError):
            pass

        out: List[ProcessSummary] = []
        for p in psutil.process_iter(["pid", "name", "create_time"]):
            try:
                pid = p.info["pid"]
                if pid in ProcessHunter.SELF_PIDS:
                    continue
                name = (p.info.get("name") or "").strip()
                cpu = p.cpu_percent(None)
                with p.oneshot():
                    mem = p.memory_info().rss / (1024 * 1024)
                    started = p.info.get("create_time", 0.0) or 0.0
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception:
                continue
            is_protected = name.lower() in PROTECTED_NAMES
            summary = ProcessSummary(
                pid=pid,
                name=name,
                cpu_percent=cpu,
                ram_mb=mem,
                network_connections=conns_by_pid.get(pid, 0),
                is_protected=is_protected,
                is_self=False,
                started_at=started,
            )
            self._tag_suggestion(summary)
            out.append(summary)

        # Score = weighted blend; ranks "noisy" stuff first.
        out.sort(key=lambda s: (
            s.is_protected,            # protected sinks last
            -(s.cpu_percent + s.ram_mb / 50.0 + s.network_connections * 0.5),
        ))
        return out

    @staticmethod
    def _tag_suggestion(s: ProcessSummary) -> None:
        if s.is_protected:
            return
        rule = _BACKGROUND_TAMERS.get(s.name.lower())
        if rule is not None:
            s.suggestion = rule.preferred_action
            s.suggestion_reason = rule.reason
            return
        if s.cpu_percent >= 25:
            s.suggestion = "lower_priority"
            s.suggestion_reason = f"Using {s.cpu_percent:.0f}% CPU."
        elif s.ram_mb >= 1500:
            s.suggestion = "kill"
            s.suggestion_reason = f"Using {s.ram_mb:.0f} MB RAM."


# ============================================================================
# Manager — applies + reverses suspend / priority / kill operations
# ============================================================================
@dataclass
class ProcessActionRecord:
    pid: int
    name: str
    action: str                  # "suspend" | "lower_priority" | "kill"
    previous_priority: Optional[int] = None  # nice value before lowering


class ProcessActionManager:
    """Apply (and reverse, where possible) per-process actions."""

    def __init__(self, history: Optional[ActionHistory] = None) -> None:
        self._history = history
        self._suspended: List[ProcessActionRecord] = []
        self._priority_lowered: List[ProcessActionRecord] = []

    def suspended(self) -> List[ProcessActionRecord]:
        return list(self._suspended)

    def lowered(self) -> List[ProcessActionRecord]:
        return list(self._priority_lowered)

    # ----------------------------------------------------------- operations
    def suspend(self, pid: int) -> bool:
        try:
            p = psutil.Process(pid)
            name = p.name()
            if name.lower() in PROTECTED_NAMES:
                return False
            p.suspend()
            rec = ProcessActionRecord(pid=pid, name=name, action="suspend")
            self._suspended.append(rec)
            self._record(rec, summary=f"Suspended {name} (pid {pid})")
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        except Exception:
            log.exception("suspend(pid=%d) failed", pid)
            return False

    def resume(self, pid: int) -> bool:
        try:
            psutil.Process(pid).resume()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception:
            log.exception("resume(pid=%d) failed", pid)
        self._suspended = [r for r in self._suspended if r.pid != pid]
        return True

    def resume_all(self) -> None:
        for rec in list(self._suspended):
            self.resume(rec.pid)

    def lower_priority(self, pid: int) -> bool:
        try:
            p = psutil.Process(pid)
            name = p.name()
            if name.lower() in PROTECTED_NAMES:
                return False
            prev = p.nice()
            target = self._below_normal()
            if sys.platform == "win32":
                # On Windows nice() returns a priority *class* int.
                p.nice(target)
            else:
                p.nice(min(19, max(prev, 10)))
            rec = ProcessActionRecord(
                pid=pid, name=name, action="lower_priority", previous_priority=prev,
            )
            self._priority_lowered.append(rec)
            self._record(rec, summary=f"Lowered priority of {name} (pid {pid})")
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        except Exception:
            log.exception("lower_priority(pid=%d) failed", pid)
            return False

    def restore_priority(self, pid: int) -> bool:
        rec = next((r for r in self._priority_lowered if r.pid == pid), None)
        if rec is None or rec.previous_priority is None:
            return False
        try:
            psutil.Process(pid).nice(rec.previous_priority)
        except Exception:
            log.exception("restore_priority(pid=%d) failed", pid)
            return False
        self._priority_lowered = [r for r in self._priority_lowered if r.pid != pid]
        return True

    def restore_all_priorities(self) -> None:
        for rec in list(self._priority_lowered):
            self.restore_priority(rec.pid)

    def kill(self, pid: int) -> bool:
        try:
            p = psutil.Process(pid)
            name = p.name()
            if name.lower() in PROTECTED_NAMES:
                return False
            p.terminate()
            try:
                p.wait(timeout=2)
            except psutil.TimeoutExpired:
                p.kill()
            rec = ProcessActionRecord(pid=pid, name=name, action="kill")
            self._record(rec, summary=f"Killed {name} (pid {pid})")
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        except Exception:
            log.exception("kill(pid=%d) failed", pid)
            return False

    # ----------------------------------------------------------- internals
    @staticmethod
    def _below_normal() -> int:
        """Cross-platform "below normal" priority hint."""
        if sys.platform == "win32":
            try:
                return psutil.BELOW_NORMAL_PRIORITY_CLASS  # type: ignore[attr-defined]
            except AttributeError:
                return 16384  # Win32 BELOW_NORMAL_PRIORITY_CLASS
        return 10

    def _record(self, rec: ProcessActionRecord, *, summary: str) -> None:
        if self._history is None:
            return
        try:
            self._history.add(ActionRecord.new(
                category="process",
                action=f"process.{rec.action}",
                summary=summary,
                risk="low",
                reversible=rec.action != "kill",
                payload={
                    "pid": rec.pid,
                    "name": rec.name,
                    "previous_priority": rec.previous_priority,
                },
            ))
        except Exception:
            log.exception("failed to record process.%s in history", rec.action)


# ============================================================================
# Background App Tamer — surfaces curated rules, hands off to manager
# ============================================================================
@dataclass
class TamerCandidate:
    pid: int
    name: str
    rule: TamerRule
    ram_mb: float
    cpu_percent: float


class BackgroundAppTamer:
    """Match running processes against the curated tamer rules."""

    def __init__(self, manager: Optional[ProcessActionManager] = None) -> None:
        self._manager = manager or ProcessActionManager()

    @property
    def manager(self) -> ProcessActionManager:
        return self._manager

    def candidates(self) -> List[TamerCandidate]:
        """Find running processes that match the curated tamer list."""
        out: List[TamerCandidate] = []
        for p in psutil.process_iter(["pid", "name"]):
            try:
                name = (p.info.get("name") or "").lower()
                if name in PROTECTED_NAMES:
                    continue
                rule = _BACKGROUND_TAMERS.get(name)
                if rule is None:
                    continue
                with p.oneshot():
                    mem = p.memory_info().rss / (1024 * 1024)
                    cpu = p.cpu_percent(None)
                out.append(TamerCandidate(
                    pid=p.info["pid"],
                    name=name,
                    rule=rule,
                    ram_mb=mem,
                    cpu_percent=cpu,
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception:
                continue
        out.sort(key=lambda c: (c.rule.safety != "safe", -c.ram_mb))
        return out

    def tame(self, candidate: TamerCandidate) -> bool:
        action = candidate.rule.preferred_action
        if action == "suspend":
            return self._manager.suspend(candidate.pid)
        if action == "lower_priority":
            return self._manager.lower_priority(candidate.pid)
        if action == "kill":
            return self._manager.kill(candidate.pid)
        return False

    def restore_all(self) -> None:
        self._manager.resume_all()
        self._manager.restore_all_priorities()


def all_tamer_rules() -> List[TamerRule]:
    return list(_BACKGROUND_TAMERS.values())
