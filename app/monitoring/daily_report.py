"""Daily Performance Report — rolls up the previous day's activity into
a single card the user sees on the Dashboard.

Persistence: ``reports/daily.jsonl`` — one record per day. Aggregation
runs on app start and once a day at midnight (timer driven by the UI
layer; this module just exposes pure-function builders).
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

from ..safety.action_history import ActionHistory, ActionRecord
from ..utils.logger import get_logger
from ..utils.paths import REPORTS_DIR, ensure_app_dirs

log = get_logger("monitoring.daily_report")

_FILENAME = "daily.jsonl"


@dataclass
class DailyReport:
    """One day worth of aggregated metrics."""
    date: str                                    # YYYY-MM-DD (local)
    plans_applied: int = 0
    cleanup_mb_freed: float = 0.0
    memory_mb_freed: float = 0.0
    boost_minutes: int = 0
    game_mode_minutes: int = 0
    optimizations_total: int = 0
    fps_samples: int = 0
    fps_avg: float = 0.0
    fps_low_1pct: float = 0.0
    games_played: List[str] = field(default_factory=list)
    notable_event: str = ""                      # one-line summary for the card

    @classmethod
    def empty(cls, date: str) -> "DailyReport":
        return cls(date=date)


class DailyReportService:
    """Builds reports from :class:`ActionHistory` + cached FPS data."""

    def __init__(self, history: ActionHistory, *, path: Optional[Path] = None) -> None:
        ensure_app_dirs()
        self._history = history
        self._path = path or (REPORTS_DIR / _FILENAME)
        self._cache: List[DailyReport] = self._load()

    # ------------------------------------------------------------------ public
    def latest(self) -> Optional[DailyReport]:
        return self._cache[-1] if self._cache else None

    def all(self) -> List[DailyReport]:
        return list(self._cache)

    def get(self, date: str) -> Optional[DailyReport]:
        for r in self._cache:
            if r.date == date:
                return r
        return None

    def regenerate_today(self, *, fps_samples: Iterable[float] = ()) -> DailyReport:
        """Recompute today's report from scratch and persist."""
        today = dt.date.today().isoformat()
        rep = self._build_for_date(today, fps_samples=list(fps_samples))
        self._upsert(rep)
        return rep

    def regenerate_for(self, date: str, *, fps_samples: Iterable[float] = ()) -> DailyReport:
        rep = self._build_for_date(date, fps_samples=list(fps_samples))
        self._upsert(rep)
        return rep

    # ------------------------------------------------------------------ builders
    def _build_for_date(self, date: str, *, fps_samples: List[float]) -> DailyReport:
        # ActionHistory is in-memory; filter records by local date
        start = dt.datetime.fromisoformat(date).timestamp()
        end = start + 86400
        rep = DailyReport.empty(date)
        records = [r for r in self._history.all() if start <= r.ts < end]

        for rec in records:
            self._fold_record(rep, rec)

        rep.optimizations_total = rep.plans_applied
        rep.fps_samples = len(fps_samples)
        if fps_samples:
            rep.fps_avg = sum(fps_samples) / len(fps_samples)
            sorted_samples = sorted(fps_samples)
            idx = max(0, int(len(sorted_samples) * 0.01))
            rep.fps_low_1pct = sorted_samples[idx]

        rep.notable_event = self._summarize(rep)
        return rep

    @staticmethod
    def _fold_record(rep: DailyReport, rec: ActionRecord) -> None:
        if rec.category == "optimize" and rec.status == "applied":
            rep.plans_applied += 1
        elif rec.category == "cleanup" and rec.status == "applied":
            mb = float(rec.payload.get("mb_freed", 0.0))
            rep.cleanup_mb_freed += mb
        elif rec.category == "memory":
            mb = float(rec.payload.get("freed_mb", 0.0))
            rep.memory_mb_freed += mb
        elif rec.category == "boost":
            if rec.action == "boost_start":
                # Will pair with the next boost_stop in a separate scan.
                pass
        elif rec.category == "gamemode":
            if rec.action == "gamemode_off":
                minutes = int(rec.payload.get("duration_s", 0)) // 60
                rep.game_mode_minutes += minutes
                game = str(rec.payload.get("game", "")).strip()
                if game and game not in rep.games_played:
                    rep.games_played.append(game)

    @staticmethod
    def _summarize(rep: DailyReport) -> str:
        bits: List[str] = []
        if rep.fps_samples and rep.fps_avg:
            bits.append(f"{rep.fps_avg:.0f} FPS avg")
        if rep.cleanup_mb_freed:
            bits.append(f"cleaned {rep.cleanup_mb_freed:.0f} MB")
        if rep.memory_mb_freed:
            bits.append(f"trimmed {rep.memory_mb_freed:.0f} MB RAM")
        if rep.plans_applied:
            bits.append(f"{rep.plans_applied} plan{'s' if rep.plans_applied > 1 else ''} applied")
        if rep.game_mode_minutes:
            hrs = rep.game_mode_minutes / 60
            bits.append(f"{hrs:.1f} h gaming")
        return " · ".join(bits) if bits else "Quiet day — no optimizations needed"

    # ------------------------------------------------------------------ io
    def _upsert(self, rep: DailyReport) -> None:
        for i, existing in enumerate(self._cache):
            if existing.date == rep.date:
                self._cache[i] = rep
                self._rewrite()
                return
        self._cache.append(rep)
        try:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(rep)) + "\n")
        except Exception:
            log.exception("Failed to append daily report")

    def _rewrite(self) -> None:
        try:
            with self._path.open("w", encoding="utf-8") as fh:
                for rep in self._cache:
                    fh.write(json.dumps(asdict(rep)) + "\n")
        except Exception:
            log.exception("Failed to rewrite daily reports")

    def _load(self) -> List[DailyReport]:
        if not self._path.exists():
            return []
        out: List[DailyReport] = []
        try:
            for line in self._path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                out.append(DailyReport(**json.loads(line)))
        except Exception:
            log.exception("Failed to load daily reports; starting fresh")
            return []
        return out
