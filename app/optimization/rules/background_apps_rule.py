"""Background app analysis.

Looks for common high-RAM consumers (browsers, chat apps, launchers) and
flags how much memory could be freed if the user closes them before gaming.
Does not kill processes — that's Game Mode's job with explicit opt-in.
"""
from __future__ import annotations

from typing import Any, Dict, List

import psutil

from ...core.constants import IMPACT_MODERATE, RISK_SAFE
from ...system.hardware_detector import HardwareSnapshot
from ...utils.formatting import human_bytes
from ...utils.logger import get_logger
from .base_rule import OptimizationRule, RuleEvaluation, RuleOutcome

log = get_logger("opt.background_apps")

# Process-name patterns commonly worth closing before a heavy game.
# Matched case-insensitively on the process name. Browsers first.
_HEAVY_PATTERNS = [
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe",
    "discord.exe", "slack.exe", "teams.exe", "skype.exe", "zoom.exe",
    "spotify.exe", "onedrive.exe", "dropbox.exe",
    "epicgameslauncher.exe", "eastore.exe", "battlenet.exe", "steamwebhelper.exe",
    "obs64.exe", "obs32.exe",
]


class BackgroundAppsRule(OptimizationRule):
    id = "background.review_heavy_apps"
    title = "Close memory-hungry background apps"
    category = "services"
    what = (
        "Detects common apps that typically eat several GB of RAM (browsers, "
        "chat clients, cloud sync). Reports how much memory they're currently "
        "using so you know the real cost of leaving them open."
    )
    why = (
        "Modern titles are memory-hungry. A 3 GB Chrome session + Discord + "
        "OneDrive can push a 16 GB machine into paging territory during a raid. "
        "Closing these before play routinely reclaims 2–4 GB."
    )
    risk = RISK_SAFE
    impact = IMPACT_MODERATE
    reversible = False
    advisory = True

    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        offenders = self._scan()
        total_bytes = sum(o["rss"] for o in offenders)
        if not offenders or total_bytes < 500 * 1024 * 1024:
            return RuleEvaluation(False, "No heavy background apps worth calling out.",
                                   evidence={"offenders": offenders})
        score = min(85, int(total_bytes / (1024 * 1024 * 128)))   # ~1 point per 128 MB
        return RuleEvaluation(
            True,
            f"Background apps using about {human_bytes(total_bytes)} of RAM.",
            score=max(score, 30),
            evidence={"offenders": offenders, "bytes": total_bytes},
        )

    def apply(self) -> RuleOutcome:
        return RuleOutcome(True, "Offenders reported — close manually or use Game Mode.")

    def restore(self, payload: Dict[str, Any]) -> None:  # pragma: no cover
        return None

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _scan() -> List[dict]:
        grouped: Dict[str, dict] = {}
        for proc in psutil.process_iter(attrs=["name", "memory_info"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if not name or name not in _HEAVY_PATTERNS:
                    continue
                rss = proc.info["memory_info"].rss if proc.info.get("memory_info") else 0
                entry = grouped.setdefault(name, {"name": name, "rss": 0, "count": 0})
                entry["rss"] += rss
                entry["count"] += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        offenders = sorted(grouped.values(), key=lambda e: e["rss"], reverse=True)
        return offenders
