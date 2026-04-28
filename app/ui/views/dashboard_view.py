"""Dashboard — the landing screen.

Layout:

  ┌──────────────── Hero (readiness + CTAs) ─────────────────┐
  │ [ring]  Welcome back    [Analyze] [Game Mode]           │
  └───────────────────────────────────────────────────────────┘
  ┌─────── Perf grid (CPU / RAM / Disk / Net) ────────────────┐
  │  card   card   card   card                                │
  └───────────────────────────────────────────────────────────┘
  ┌── Machine at a glance ──┐  ┌── Issues & recommendations ──┐
  │  spec rows              │  │  bottleneck cards            │
  └─────────────────────────┘  └──────────────────────────────┘
"""
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...core.app_controller import AppController
from ...monetization import AdBanner
from ...monitoring.performance_monitor import MetricSample
from ...system.hardware_detector import HardwareSnapshot
from ...utils.formatting import human_bytes
from ..theme.palette import Palette
from ..theme.typography import Typography
from ..viewmodels.monitor_vm import MonitorViewModel
from ..widgets.badge import Badge
from ..widgets.hero_card import HeroCard
from ..widgets.live_insights_panel import LiveInsightsPanel
from ..widgets.perf_card import PerfCard
from ..widgets.section import Card, SectionHeader, StatRow


class DashboardView(QWidget):
    analyze_requested = pyqtSignal()
    game_mode_requested = pyqtSignal()
    navigation_requested = pyqtSignal(str)   # view id: "optimize" | "game_mode" | "cleanup"

    def __init__(
        self,
        controller: AppController,
        monitor_vm: MonitorViewModel,
        palette: Palette,
        typography: Typography,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._ctrl = controller
        self._pal = palette
        self._type = typography

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        root = QVBoxLayout(container)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(22)

        # -- Hero
        self.hero = HeroCard(palette=palette, typography=typography)
        self.hero.primary_clicked.connect(self.analyze_requested)
        self.hero.secondary_clicked.connect(self.game_mode_requested)
        root.addWidget(self.hero)

        # -- Perf cards header
        root.addWidget(SectionHeader(
            "LIVE TELEMETRY", "Real-time performance",
            palette=palette, typography=typography,
        ))

        # -- Perf grid (4 cards)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        self.cpu_card = PerfCard(palette=palette, typography=typography, eyebrow="CPU",    accent=palette.chart_cpu)
        self.ram_card = PerfCard(palette=palette, typography=typography, eyebrow="Memory", accent=palette.chart_ram)
        self.disk_card = PerfCard(palette=palette, typography=typography, eyebrow="Disk",   accent=palette.chart_disk)
        self.net_card = PerfCard(palette=palette, typography=typography, eyebrow="Network", accent=palette.chart_gpu, unit="")

        grid.addWidget(self.cpu_card, 0, 0)
        grid.addWidget(self.ram_card, 0, 1)
        grid.addWidget(self.disk_card, 1, 0)
        grid.addWidget(self.net_card, 1, 1)
        root.addLayout(grid)

        # -- Live Insights panel (adaptive, re-renders on every sample)
        self.live_insights = LiveInsightsPanel(
            bus=controller.bus,
            palette=palette,
            typography=typography,
            initial=controller.live_insights.latest(),
        )
        self.live_insights.navigation_requested.connect(self.navigation_requested.emit)
        root.addWidget(self.live_insights)

        # -- Two-column: Specs + Recommendations
        columns = QHBoxLayout()
        columns.setSpacing(16)

        # Spec card
        self.spec_card = Card(palette=palette, padding=22)
        spec_header = SectionHeader(
            "Machine at a glance", "Your hardware",
            palette=palette, typography=typography,
            eyebrow_color=palette.violet,
        )
        self.spec_card.body().addWidget(spec_header)
        self._spec_cpu = StatRow("CPU", "Detecting…", palette=palette, typography=typography)
        self._spec_gpu = StatRow("GPU", "Detecting…", palette=palette, typography=typography)
        self._spec_ram = StatRow("Memory", "Detecting…", palette=palette, typography=typography)
        self._spec_os = StatRow("OS", "Detecting…", palette=palette, typography=typography)
        self._spec_disk = StatRow("System drive", "Detecting…", palette=palette, typography=typography)
        self.spec_card.body().addWidget(self._spec_cpu)
        self.spec_card.body().addWidget(self._spec_gpu)
        self.spec_card.body().addWidget(self._spec_ram)
        self.spec_card.body().addWidget(self._spec_os)
        self.spec_card.body().addWidget(self._spec_disk)
        self.spec_card.body().addStretch()
        columns.addWidget(self.spec_card, 1)

        # Recommendations card
        self.issues_card = Card(palette=palette, padding=22)
        issues_header = SectionHeader(
            "Observations", "Issues & recommendations",
            palette=palette, typography=typography,
            eyebrow_color=palette.amber,
        )
        self.issues_card.body().addWidget(issues_header)

        self._issues_container = QVBoxLayout()
        self._issues_container.setSpacing(10)
        self.issues_card.body().addLayout(self._issues_container)
        self._empty_issues = QLabel("No issues detected yet — run an analysis to populate this panel.")
        self._empty_issues.setWordWrap(True)
        self._empty_issues.setFont(typography.body())
        self._empty_issues.setStyleSheet(f"color: {palette.text_secondary};")
        self._issues_container.addWidget(self._empty_issues)
        self.issues_card.body().addStretch()
        columns.addWidget(self.issues_card, 1)

        root.addLayout(columns)

        # -- Sponsored banner (self-hides if ads_enabled=False)
        self.ad_banner = AdBanner(controller.config, palette, typography, slot="dashboard")
        root.addWidget(self.ad_banner)

        root.addStretch()

        # -- Bind monitor samples to the live cards
        monitor_vm.sampled.connect(self._on_sample)
        monitor_vm.hardware_ready.connect(self.update_hardware)

    # ------------------------------------------------------------------ public
    def update_hardware(self, snapshot: HardwareSnapshot) -> None:
        cpu = snapshot.cpu
        cpu_line = cpu.name.strip() or "Unknown CPU"
        if cpu.cores_physical:
            cpu_line += f"  ·  {cpu.cores_physical}C / {cpu.cores_logical}T"
        if cpu.max_mhz:
            cpu_line += f"  ·  up to {cpu.max_mhz / 1000:0.1f} GHz"
        self._spec_cpu.setValue(cpu_line)

        gpu = snapshot.primary_gpu
        gpu_line = gpu.name
        if gpu.vram_mb:
            gpu_line += f"  ·  {gpu.vram_mb} MB VRAM"
        if gpu.driver_version:
            gpu_line += f"  ·  driver {gpu.driver_version}"
        self._spec_gpu.setValue(gpu_line)

        ram_line = human_bytes(snapshot.ram.total_bytes or 0)
        if snapshot.ram.modules:
            ram_line += f"  ·  {snapshot.ram.modules} module(s)"
        if snapshot.ram.speed_mhz:
            ram_line += f"  @ {snapshot.ram.speed_mhz} MT/s"
        self._spec_ram.setValue(ram_line)

        os_info = snapshot.os
        self._spec_os.setValue(f"{os_info.system} {os_info.release}  ·  build {os_info.version}")

        if snapshot.disks:
            main = snapshot.disks[0]
            used = main.total_bytes - main.free_bytes
            pct = (used / main.total_bytes * 100) if main.total_bytes else 0
            self._spec_disk.setValue(
                f"{main.mountpoint}  ·  {human_bytes(used)} used / {human_bytes(main.total_bytes)}  "
                f"({pct:0.0f}% full)"
            )

    def set_issues(self, bottlenecks: list) -> None:
        while self._issues_container.count():
            item = self._issues_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if not bottlenecks:
            lbl = QLabel("No significant issues detected. You're in good shape.")
            lbl.setWordWrap(True)
            lbl.setFont(self._type.body())
            lbl.setStyleSheet(f"color: {self._pal.text_secondary};")
            self._issues_container.addWidget(lbl)
            return
        for b in bottlenecks[:5]:
            self._issues_container.addWidget(self._issue_widget(b))

    def set_readiness(self, score: float) -> None:
        self.hero.set_readiness(score)

    # ------------------------------------------------------------------ internals
    def _on_sample(self, sample: MetricSample) -> None:
        # CPU
        cpu_sub = f"{sample.cpu_freq_mhz / 1000:0.1f} GHz  ·  {sample.process_count} processes"
        self.cpu_card.set_value(sample.cpu_percent, subtitle=cpu_sub)
        # RAM
        ram_sub = human_bytes(sample.ram_used_bytes) + " in use"
        self.ram_card.set_value(sample.ram_percent, subtitle=ram_sub)
        # Disk (percent-based approx; show R/W rates in subtitle)
        disk_sub = f"↓ {human_bytes(sample.disk_read_bps)}/s   ↑ {human_bytes(sample.disk_write_bps)}/s"
        self.disk_card.set_value(sample.disk_percent, subtitle=disk_sub)
        # Network: headline shows actual total throughput; sparkline uses a
        # log-like normalisation so spikes are visible without clipping.
        import math

        total_bps = sample.net_down_bps + sample.net_up_bps
        norm = 0.0 if total_bps <= 0 else min(100.0, math.log10(total_bps + 1) * 12)
        self.net_card.set_text_value(
            f"{human_bytes(total_bps)}/s",
            graph_value=norm,
            subtitle=f"↓ {human_bytes(sample.net_down_bps)}/s   ↑ {human_bytes(sample.net_up_bps)}/s",
            trend="",
        )

    def _issue_widget(self, bottleneck) -> QWidget:
        wrap = QFrame()
        wrap.setProperty("role", "card-inset")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(8)
        severity_color = {"info": self._pal.accent, "warn": self._pal.amber, "critical": self._pal.coral}.get(
            bottleneck.severity, self._pal.text_secondary
        )
        tag = Badge(bottleneck.component, palette=self._pal,
                    fg=severity_color,
                    bg=self._pal.risk_dim("medium" if bottleneck.severity == "warn" else
                                          "high" if bottleneck.severity == "critical" else "safe"))
        header.addWidget(tag)
        title = QLabel(bottleneck.headline)
        title.setFont(self._type.body_strong())
        header.addWidget(title, 1)
        lay.addLayout(header)

        detail = QLabel(bottleneck.detail)
        detail.setWordWrap(True)
        detail.setFont(self._type.small())
        detail.setStyleSheet(f"color: {self._pal.text_secondary};")
        lay.addWidget(detail)

        return wrap
