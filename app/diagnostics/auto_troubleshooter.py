"""Auto-Troubleshooter — symptom-first diagnostic wizard.

The user picks a :class:`Symptom` ("My game stutters", "My PC takes
forever to boot"), the wizard runs the relevant inspectors / analyzers,
and emits a structured :class:`Diagnosis`:

* **likely cause** — top-ranked finding with confidence
* **steps** — ordered, actionable list (each step is either an existing
  optimization rule we can apply, or a manual instruction with a
  one-click "Mark as done" toggle)

This is the consumer-facing wrapper around the analyzers + inspectors
we built in earlier batches. Pure orchestration; it owns no state of
its own beyond the active diagnosis.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from ..monitoring.analyzers.predictive_maintenance import (
    MaintenancePrediction,
    PredictiveMaintenance,
)
from ..monitoring.boot_time import BootTimeService
from ..system.inspectors import (
    DriverAuditor,
    Finding,
    FindingSeverity,
    NvmeHealthInspector,
    PcieLinkInspector,
    RamXmpInspector,
)


class Symptom(enum.Enum):
    GAME_STUTTERS = "stutter"
    LOW_FPS = "low_fps"
    HIGH_LATENCY = "high_latency"
    SLOW_BOOT = "slow_boot"
    SYSTEM_HOT = "system_hot"
    RANDOM_FREEZES = "freezes"


@dataclass
class TroubleshootStep:
    """One actionable line in the wizard."""
    id: str
    title: str
    detail: str
    confidence: int = 50           # 0..100
    rule_id: Optional[str] = None  # if present, the engine can auto-apply
    manual: bool = False           # True ⇒ user does it themselves


@dataclass
class Diagnosis:
    symptom: Symptom
    summary: str
    steps: List[TroubleshootStep] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    predictions: List[MaintenancePrediction] = field(default_factory=list)


# ---------------------------------------------------------------- wizard
class Troubleshooter:
    """Run a diagnosis for a symptom.

    Inspectors are injected so the UI / tests can swap them.
    """

    def __init__(
        self,
        *,
        ram_inspector: Optional[RamXmpInspector] = None,
        pcie_inspector: Optional[PcieLinkInspector] = None,
        nvme_inspector: Optional[NvmeHealthInspector] = None,
        driver_auditor: Optional[DriverAuditor] = None,
        boot_service: Optional[BootTimeService] = None,
        predictive: Optional[PredictiveMaintenance] = None,
    ) -> None:
        self._ram = ram_inspector or RamXmpInspector()
        self._pcie = pcie_inspector or PcieLinkInspector()
        self._nvme = nvme_inspector or NvmeHealthInspector()
        self._drivers = driver_auditor or DriverAuditor()
        self._boot = boot_service or BootTimeService()
        self._predictive = predictive or PredictiveMaintenance(
            nvme=self._nvme, boot=self._boot,
        )

    # ------------------------------------------------------------------ public
    def diagnose(self, symptom: Symptom) -> Diagnosis:
        diag = Diagnosis(symptom=symptom, summary="")
        if symptom is Symptom.GAME_STUTTERS:
            self._diagnose_stutter(diag)
        elif symptom is Symptom.LOW_FPS:
            self._diagnose_low_fps(diag)
        elif symptom is Symptom.HIGH_LATENCY:
            self._diagnose_latency(diag)
        elif symptom is Symptom.SLOW_BOOT:
            self._diagnose_slow_boot(diag)
        elif symptom is Symptom.SYSTEM_HOT:
            self._diagnose_thermal(diag)
        elif symptom is Symptom.RANDOM_FREEZES:
            self._diagnose_freezes(diag)
        diag.summary = self._summarize(diag)
        return diag

    # ------------------------------------------------------------------ symptom handlers
    def _diagnose_stutter(self, diag: Diagnosis) -> None:
        # 1. RAM at wrong speed → 1% lows can collapse on RAM-heavy games
        diag.findings.extend(self._ram.inspect())
        # 2. SSD high wear / errors → texture-streaming stutter
        diag.findings.extend(self._nvme.inspect())
        # 3. Old GPU driver → known stutter fixes in newer drivers
        driver_findings = [f for f in self._drivers.inspect() if f.id == "drivers.outdated"]
        diag.findings.extend(driver_findings)

        diag.steps.append(TroubleshootStep(
            id="apply_game_mode",
            title="Activate Game Mode for the next session",
            detail="Pin foreground priority, disable Game DVR, switch to Ultimate Performance.",
            confidence=80,
            rule_id="gamemode.activate",
        ))
        diag.steps.append(TroubleshootStep(
            id="memory_trim",
            title="Trim memory before launching",
            detail="Free standby cache + working sets. Reduces texture-streaming hitches.",
            confidence=75,
            rule_id="memory.trim",
        ))
        diag.steps.append(TroubleshootStep(
            id="close_background",
            title="Close background apps",
            detail="Open Process Hunter and tame Discord, Chrome, OneDrive, etc.",
            confidence=70,
            manual=True,
        ))
        for finding in diag.findings:
            diag.steps.append(self._step_from_finding(finding))

    def _diagnose_low_fps(self, diag: Diagnosis) -> None:
        diag.findings.extend(self._pcie.inspect())
        diag.findings.extend(self._ram.inspect())
        driver_findings = [f for f in self._drivers.inspect() if f.id == "drivers.outdated"]
        diag.findings.extend(driver_findings)
        diag.steps.append(TroubleshootStep(
            id="apply_max_perf",
            title="Apply the Max Performance plan",
            detail="Unleash CPU/GPU power limits, MMCSS, and timer resolution tweaks.",
            confidence=85,
            rule_id="plan.max_performance",
        ))
        diag.steps.append(TroubleshootStep(
            id="enable_xmp",
            title="Enable XMP / EXPO in BIOS",
            detail="If your kit supports a higher rated speed, this is usually free 5-15% in 1% lows.",
            confidence=60,
            manual=True,
        ))
        for finding in diag.findings:
            diag.steps.append(self._step_from_finding(finding))

    def _diagnose_latency(self, diag: Diagnosis) -> None:
        diag.steps.append(TroubleshootStep(
            id="run_dns_benchmark",
            title="Benchmark DNS resolvers",
            detail="Switching to the fastest free public DNS often shaves 10-40 ms off matchmaking.",
            confidence=80,
            manual=True,
        ))
        diag.steps.append(TroubleshootStep(
            id="run_ping_test",
            title="Ping game server regions",
            detail="Find your lowest-RTT region and pick that in the in-game server menu.",
            confidence=80,
            manual=True,
        ))
        diag.steps.append(TroubleshootStep(
            id="apply_network_rules",
            title="Apply network latency rules",
            detail="Disable Nagle, network throttling, and Windows packet coalescing.",
            confidence=70,
            rule_id="plan.network",
        ))

    def _diagnose_slow_boot(self, diag: Diagnosis) -> None:
        diag.predictions.extend(self._predictive.predictions())
        diag.steps.append(TroubleshootStep(
            id="trim_startup",
            title="Trim startup programs",
            detail="Disable anything that runs at login but you don't actively need on first boot.",
            confidence=85,
            rule_id="startup.programs",
        ))
        diag.steps.append(TroubleshootStep(
            id="disable_sysmain",
            title="Disable SuperFetch / SysMain",
            detail="On NVMe + 16+ GB RAM, SysMain churns more than it helps.",
            confidence=70,
            rule_id="services.sysmain_off",
        ))

    def _diagnose_thermal(self, diag: Diagnosis) -> None:
        diag.findings.extend(self._nvme.inspect())
        diag.steps.append(TroubleshootStep(
            id="check_drivers",
            title="Update GPU + chipset drivers",
            detail="Old drivers waste energy as heat. Driver Auditor lists the vendor links.",
            confidence=70,
            manual=True,
        ))
        diag.steps.append(TroubleshootStep(
            id="reduce_max_state",
            title="Cap CPU max processor state at 99%",
            detail="Disables turbo boost — a quick 5-10 °C reduction at small FPS cost.",
            confidence=65,
            rule_id="power.min_processor_state",
        ))

    def _diagnose_freezes(self, diag: Diagnosis) -> None:
        diag.findings.extend(self._nvme.inspect())
        diag.findings.extend(self._ram.inspect())
        diag.predictions.extend(self._predictive.predictions())
        diag.steps.append(TroubleshootStep(
            id="run_chkdsk",
            title="Run a disk health check",
            detail="Open an admin terminal and run `chkdsk C: /scan` (online, non-destructive).",
            confidence=60,
            manual=True,
        ))
        diag.steps.append(TroubleshootStep(
            id="memory_test",
            title="Run Windows Memory Diagnostic",
            detail="Type 'mdsched' into Start. The PC reboots, tests RAM, then logs back in.",
            confidence=60,
            manual=True,
        ))

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _step_from_finding(finding: Finding) -> TroubleshootStep:
        confidence = {
            FindingSeverity.INFO: 40,
            FindingSeverity.SUGGESTION: 55,
            FindingSeverity.WARNING: 70,
            FindingSeverity.CRITICAL: 90,
        }.get(finding.severity, 50)
        return TroubleshootStep(
            id=f"finding_{finding.id}",
            title=finding.title,
            detail=f"{finding.detail} {finding.fix_hint}".strip(),
            confidence=confidence,
            manual=True,
        )

    @staticmethod
    def _summarize(diag: Diagnosis) -> str:
        if not diag.steps:
            return "No actionable issues detected. Try the manual checks above."
        top = diag.steps[0]
        return f"Most likely fix: {top.title}"
