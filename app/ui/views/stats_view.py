"""Stats view — streaks, achievements, daily reports, boot times."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from ...engagement.achievements import Achievement, AchievementService, AchievementProgress
from ...engagement.streaks import StreakService
from ...monitoring.boot_time import BootTimeService
from ...monitoring.daily_report import DailyReport, DailyReportService
from ..theme.palette import Palette
from ..theme.typography import Typography
from ..widgets.banner import Banner
from ..widgets.section import Card, SectionHeader


class StatsView(QWidget):
    def __init__(self, controller, palette: Palette, typography: Typography, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._pal = palette
        self._type = typography

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, stretch=1)

        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(body)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(20)

        root.addWidget(SectionHeader(
            "STATS", "Your performance journey",
            palette=palette, typography=typography,
        ))

        # Snapshot row: streak / unlocked count / boot time
        root.addLayout(self._build_snapshot_row())
        root.addWidget(self._build_daily_card())
        root.addWidget(self._build_achievements())
        root.addWidget(self._build_boot_history())
        root.addStretch(1)

    # ----------------------------------------------------------------- helpers
    def refresh(self) -> None:
        # Lightweight: rebuild stat tiles from current state.
        try:
            self._streak_value.setText(str(self._streak_state().current_streak))
            self._streak_best.setText(f"Best: {self._streak_state().longest_streak}")
        except Exception:
            pass

    def _streak_state(self):
        svc: StreakService = self._ctrl.streaks
        # record_open is idempotent for the same day; safe to call here so
        # users always see the up-to-date streak when opening the tab.
        try:
            return svc.record_open()
        except Exception:
            return svc.state

    # ----------------------------------------------------------------- panels
    def _build_snapshot_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        # Streak tile
        streak_state = self._streak_state()
        streak_card = self._stat_tile(
            eyebrow="DAILY STREAK",
            value=str(streak_state.current_streak),
            unit="days",
            footer=f"Best: {streak_state.longest_streak}",
            color=self._pal.accent,
        )
        # keep refs for refresh()
        body = streak_card.findChildren(QLabel)
        if len(body) >= 2:
            self._streak_value = body[1]
        if len(body) >= 4:
            self._streak_best = body[3]
        row.addWidget(streak_card)

        # Unlocked tile
        ach: AchievementService = self._ctrl.achievements
        unlocked = len(ach.unlocked())
        total = len(ach.all())
        row.addWidget(self._stat_tile(
            eyebrow="TROPHIES",
            value=str(unlocked),
            unit=f"/ {total}",
            footer=f"{(unlocked / total * 100) if total else 0:.0f}% complete",
            color=self._pal.violet,
        ))

        # Boot time tile
        boot: BootTimeService = self._ctrl.boot_time
        latest = boot.latest()
        if latest is not None:
            secs = latest.total_ms / 1000
            footer = "Faster boots → more game-time"
            value = f"{secs:.1f}"
            unit = "sec last boot"
        else:
            value = "—"
            unit = "no data yet"
            footer = "Reboot to record a baseline"
        row.addWidget(self._stat_tile(
            eyebrow="BOOT TIME",
            value=value,
            unit=unit,
            footer=footer,
            color=self._pal.neon_blue,
        ))

        return row

    def _stat_tile(self, *, eyebrow: str, value: str, unit: str, footer: str, color: str) -> Card:
        card = Card(palette=self._pal)
        body = card.body()
        eb = QLabel(eyebrow)
        eb.setFont(self._type.micro())
        eb.setStyleSheet(f"color: {color}; letter-spacing: 2px;")
        body.addWidget(eb)

        v = QLabel(value)
        try:
            v.setFont(self._type.display_h1())
        except Exception:
            v.setFont(self._type.h1())
        v.setStyleSheet(f"color: {self._pal.text_primary};")
        body.addWidget(v)

        u = QLabel(unit)
        u.setFont(self._type.body())
        u.setStyleSheet(f"color: {self._pal.text_secondary};")
        body.addWidget(u)

        fl = QLabel(footer)
        fl.setFont(self._type.small())
        fl.setStyleSheet(f"color: {self._pal.text_tertiary};")
        body.addWidget(fl)
        return card

    def _build_daily_card(self) -> QWidget:
        card = Card(palette=self._pal)
        body = card.body()
        head = QHBoxLayout()
        title = QLabel("Today's report")
        title.setFont(self._type.h2())
        title.setStyleSheet(f"color: {self._pal.text_primary};")
        head.addWidget(title, stretch=1)

        regen_btn = QPushButton("Regenerate")
        regen_btn.setProperty("variant", "ghost")
        regen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        regen_btn.clicked.connect(self._regenerate_daily)
        head.addWidget(regen_btn)
        body.addLayout(head)

        self._daily_summary = QLabel()
        self._daily_summary.setFont(self._type.body())
        self._daily_summary.setStyleSheet(f"color: {self._pal.text_secondary};")
        self._daily_summary.setWordWrap(True)
        body.addWidget(self._daily_summary)

        self._daily_grid = QGridLayout()
        self._daily_grid.setHorizontalSpacing(20)
        self._daily_grid.setVerticalSpacing(6)
        body.addLayout(self._daily_grid)

        self._render_daily(self._daily_service().latest())
        return card

    def _daily_service(self) -> DailyReportService:
        return self._ctrl.daily_report

    def _regenerate_daily(self) -> None:
        try:
            rep = self._daily_service().regenerate_today()
        except Exception:
            rep = self._daily_service().latest()
        self._render_daily(rep)

    def _render_daily(self, rep: Optional[DailyReport]) -> None:
        # Clear grid first
        while self._daily_grid.count():
            item = self._daily_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if rep is None:
            self._daily_summary.setText(
                "No report yet. Apply some optimizations or run a cleanup to start tracking."
            )
            return
        if rep.notable_event:
            self._daily_summary.setText(f"{rep.date} · {rep.notable_event}")
        else:
            self._daily_summary.setText(rep.date)

        rows = [
            ("Plans applied", str(rep.plans_applied)),
            ("Cleanup freed", f"{rep.cleanup_mb_freed:.0f} MB"),
            ("Memory trimmed", f"{rep.memory_mb_freed:.0f} MB"),
            ("Boost minutes", f"{rep.boost_minutes}"),
            ("Game Mode", f"{rep.game_mode_minutes} min"),
            ("FPS samples", f"{rep.fps_samples}"),
        ]
        if rep.fps_avg:
            rows.append(("FPS avg", f"{rep.fps_avg:.0f}"))
        if rep.fps_low_1pct:
            rows.append(("1% lows", f"{rep.fps_low_1pct:.0f}"))

        for r, (k, v) in enumerate(rows):
            kl = QLabel(k)
            kl.setFont(self._type.small())
            kl.setStyleSheet(f"color: {self._pal.text_tertiary};")
            vl = QLabel(v)
            vl.setFont(self._type.body_strong())
            vl.setStyleSheet(f"color: {self._pal.text_primary};")
            self._daily_grid.addWidget(kl, r // 2, (r % 2) * 2)
            self._daily_grid.addWidget(vl, r // 2, (r % 2) * 2 + 1)

    def _build_achievements(self) -> QWidget:
        card = Card(palette=self._pal)
        body = card.body()
        title = QLabel("Trophies")
        title.setFont(self._type.h2())
        title.setStyleSheet(f"color: {self._pal.text_primary};")
        body.addWidget(title)

        ach: AchievementService = self._ctrl.achievements
        items = ach.all()
        progress_map = ach.progress_all()

        if not items:
            body.addWidget(self._muted("No achievements registered yet."))
            return card

        for a in items:
            p = progress_map.get(a.id)
            body.addWidget(self._achievement_row(a, p))
        return card

    def _achievement_row(self, a: Achievement, p: Optional[AchievementProgress]) -> QWidget:
        unlocked = bool(p and p.unlocked_at > 0)
        color = self._pal.accent if unlocked else self._pal.text_tertiary
        wrap = QFrame()
        wrap.setStyleSheet(
            f"QFrame {{ background: {self._pal.bg_sunken}; "
            f"border: 1px solid {self._pal.border}; border-radius: 6px; }}"
        )
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)

        icon = QLabel("[X]" if unlocked else "[ ]")
        icon.setFont(self._type.body_strong())
        icon.setStyleSheet(f"color: {color};")
        icon.setFixedWidth(28)
        lay.addWidget(icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        t = QLabel(a.title)
        t.setFont(self._type.body_strong())
        t.setStyleSheet(f"color: {self._pal.text_primary if unlocked else self._pal.text_secondary};")
        text_col.addWidget(t)

        d = QLabel(a.description)
        d.setFont(self._type.small())
        d.setStyleSheet(f"color: {self._pal.text_tertiary};")
        d.setWordWrap(True)
        text_col.addWidget(d)
        lay.addLayout(text_col, stretch=1)

        progress_text = ""
        if p is not None:
            progress_text = f"{int(p.progress)} / {int(a.target)}"
            if a.unit:
                progress_text += f" {a.unit}"
        prog = QLabel(progress_text)
        prog.setFont(self._type.small())
        prog.setStyleSheet(f"color: {color};")
        prog.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        prog.setMinimumWidth(110)
        lay.addWidget(prog)
        return wrap

    def _build_boot_history(self) -> QWidget:
        card = Card(palette=self._pal)
        body = card.body()
        title = QLabel("Recent boots")
        title.setFont(self._type.h2())
        title.setStyleSheet(f"color: {self._pal.text_primary};")
        body.addWidget(title)

        boot: BootTimeService = self._ctrl.boot_time
        records = boot.history(limit=7)

        if not records:
            body.addWidget(self._muted(
                "No boot history yet. Reboot once for the kernel to record a sample."
            ))
            return card

        avg = boot.average_total_ms() or 0.0
        sub = QLabel(f"7-boot average: {avg / 1000:.1f}s")
        sub.setFont(self._type.body())
        sub.setStyleSheet(f"color: {self._pal.text_secondary};")
        body.addWidget(sub)

        import datetime as dt
        for r in reversed(records):
            row = QHBoxLayout()
            ts_label = QLabel(dt.datetime.fromtimestamp(r.ts).strftime("%Y-%m-%d %H:%M"))
            ts_label.setFont(self._type.small())
            ts_label.setStyleSheet(f"color: {self._pal.text_tertiary};")
            ts_label.setFixedWidth(140)
            row.addWidget(ts_label)

            secs = r.total_ms / 1000
            color = self._pal.accent if secs < 30 else (
                self._pal.amber if secs < 60 else self._pal.coral
            )
            v = QLabel(f"{secs:.1f}s")
            v.setFont(self._type.body_strong())
            v.setStyleSheet(f"color: {color};")
            row.addWidget(v)

            row.addStretch()
            wrap = QWidget()
            wrap.setLayout(row)
            body.addWidget(wrap)
        return card

    def _muted(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(self._type.body())
        lbl.setStyleSheet(f"color: {self._pal.text_secondary};")
        lbl.setWordWrap(True)
        return lbl
