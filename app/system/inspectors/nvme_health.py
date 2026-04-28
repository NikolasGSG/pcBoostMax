"""SMART / health data for NVMe and SATA drives.

Uses ``Get-PhysicalDisk`` + ``Get-StorageReliabilityCounter`` (built into
Windows PowerShell — no driver needed). For drives where the OS exposes
the counters, we pull:

* ``Wear``               — percent used (0 = brand new, 100 = end-of-life)
* ``Temperature``        — current operating temperature
* ``ReadErrorsTotal``    — uncorrected read errors
* ``WriteErrorsTotal``   — uncorrected write errors
* ``PowerOnHours``       — total hours powered

Findings:

* ``ssd.wear_warning``  — wear ≥ 80%
* ``ssd.wear_critical`` — wear ≥ 90%  (sponsored replacement card)
* ``ssd.temp_high``     — temperature ≥ 70 °C
* ``ssd.errors``        — non-zero uncorrected errors

Persistence: ``stats/ssd_health.jsonl`` — one record per drive per day
so we can compute wear-rate trends for predictive maintenance.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

from ...utils.logger import get_logger
from ...utils.paths import STATS_DIR, ensure_app_dirs
from .base import Finding, FindingSeverity, Inspector, run_powershell

log = get_logger("system.inspectors.nvme_health")

_FILENAME = "ssd_health.jsonl"


@dataclass
class NvmeHealthRecord:
    """Snapshot for one drive."""
    ts: float = 0.0
    device: str = ""
    model: str = ""
    media_type: str = ""        # "SSD" | "HDD" | "Unspecified"
    bus_type: str = ""          # "NVMe" | "SATA" | …
    size_gb: float = 0.0
    wear_percent: float = 0.0   # 0..100
    temperature_c: float = 0.0
    power_on_hours: int = 0
    read_errors: int = 0
    write_errors: int = 0


@dataclass
class NvmeHealthReport:
    drives: List[NvmeHealthRecord] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)


class NvmeHealthInspector(Inspector):
    id = "ssd.health"

    def __init__(self, *, path: Optional[Path] = None) -> None:
        ensure_app_dirs()
        self._path = path or (STATS_DIR / _FILENAME)

    def inspect(self) -> List[Finding]:
        return self.report().findings

    def report(self) -> NvmeHealthReport:
        rep = NvmeHealthReport()
        rep.drives = self._read_drives()
        for d in rep.drives:
            self._evaluate(d, rep.findings)
        # Persist a daily record per drive (idempotent within a day)
        self._persist(rep.drives)
        return rep

    def history(self, *, days: int = 30) -> List[NvmeHealthRecord]:
        if not self._path.exists():
            return []
        cutoff = (dt.datetime.now() - dt.timedelta(days=days)).timestamp()
        out: List[NvmeHealthRecord] = []
        try:
            for line in self._path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = NvmeHealthRecord(**json.loads(line))
                if rec.ts >= cutoff:
                    out.append(rec)
        except Exception:
            log.exception("Failed to load SSD health history")
            return []
        return out

    # ------------------------------------------------------------------ readers
    def _read_drives(self) -> List[NvmeHealthRecord]:
        ps = (
            "$drives = Get-PhysicalDisk; "
            "$rows = foreach ($d in $drives) { "
            "  $r = $null; "
            "  try { $r = $d | Get-StorageReliabilityCounter -ErrorAction Stop } catch { } "
            "  [PSCustomObject]@{ "
            "    Device       = $d.DeviceId; "
            "    Model        = $d.FriendlyName; "
            "    MediaType    = $d.MediaType; "
            "    BusType      = $d.BusType; "
            "    SizeGB       = [math]::Round($d.Size / 1GB, 1); "
            "    Wear         = if ($r) { $r.Wear } else { 0 }; "
            "    Temperature  = if ($r) { $r.Temperature } else { 0 }; "
            "    PowerOnHours = if ($r) { $r.PowerOnHours } else { 0 }; "
            "    ReadErrors   = if ($r) { $r.ReadErrorsTotal } else { 0 }; "
            "    WriteErrors  = if ($r) { $r.WriteErrorsTotal } else { 0 } "
            "  } "
            "}; "
            "$rows | ConvertTo-Json -Depth 2 -Compress"
        )
        raw = run_powershell(ps, timeout=15)
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            data = [data]
        ts = dt.datetime.now().timestamp()
        out: List[NvmeHealthRecord] = []
        for entry in data:
            try:
                rec = NvmeHealthRecord(
                    ts=ts,
                    device=str(entry.get("Device", "")),
                    model=str(entry.get("Model", "")).strip(),
                    media_type=str(entry.get("MediaType", "")),
                    bus_type=str(entry.get("BusType", "")),
                    size_gb=float(entry.get("SizeGB") or 0.0),
                    wear_percent=float(entry.get("Wear") or 0.0),
                    temperature_c=float(entry.get("Temperature") or 0.0),
                    power_on_hours=int(entry.get("PowerOnHours") or 0),
                    read_errors=int(entry.get("ReadErrors") or 0),
                    write_errors=int(entry.get("WriteErrors") or 0),
                )
                out.append(rec)
            except (TypeError, ValueError):
                continue
        return out

    # ------------------------------------------------------------------ findings
    @staticmethod
    def _evaluate(d: NvmeHealthRecord, out: List[Finding]) -> None:
        if d.media_type and d.media_type.lower() != "ssd":
            return  # HDD wear/temp counters aren't comparable
        if d.wear_percent >= 90:
            out.append(Finding(
                id="ssd.wear_critical",
                severity=FindingSeverity.CRITICAL,
                title=f"{d.model or d.device} is at {d.wear_percent:.0f}% wear",
                detail=(
                    "This SSD is approaching the end of its rated write life. "
                    "Drives can fail unpredictably past 90% wear — back up critical "
                    "data and plan a replacement."
                ),
                fix_hint="Back up your data tonight. Replace the drive within the next month.",
                sponsored_link_id="samsung-990-pro",
                evidence={"wear_percent": d.wear_percent, "model": d.model},
            ))
        elif d.wear_percent >= 80:
            out.append(Finding(
                id="ssd.wear_warning",
                severity=FindingSeverity.WARNING,
                title=f"{d.model or d.device} is at {d.wear_percent:.0f}% wear",
                detail=(
                    "This SSD has used most of its write endurance. It will keep "
                    "working but performance may degrade and risk grows over time."
                ),
                fix_hint="Avoid heavy write workloads (recording, big game installs). Plan a future replacement.",
                sponsored_link_id="samsung-990-pro",
                evidence={"wear_percent": d.wear_percent, "model": d.model},
            ))
        if d.temperature_c >= 70:
            out.append(Finding(
                id="ssd.temp_high",
                severity=FindingSeverity.WARNING,
                title=f"{d.model or d.device} is running hot ({d.temperature_c:.0f} °C)",
                detail="Sustained NVMe temps above 70 °C cause thermal throttling and reduce drive life.",
                fix_hint="Add or replace the M.2 heatsink. Improve airflow over the drive.",
                evidence={"temperature_c": d.temperature_c, "model": d.model},
            ))
        if d.read_errors or d.write_errors:
            out.append(Finding(
                id="ssd.errors",
                severity=FindingSeverity.CRITICAL,
                title=f"Uncorrected I/O errors on {d.model or d.device}",
                detail=(
                    f"Drive reports {d.read_errors} uncorrected read and "
                    f"{d.write_errors} uncorrected write errors. This is a strong "
                    f"signal of imminent failure."
                ),
                fix_hint="Back up immediately. Replace the drive.",
                sponsored_link_id="samsung-990-pro",
                evidence={
                    "read_errors": d.read_errors,
                    "write_errors": d.write_errors,
                    "model": d.model,
                },
            ))

    # ------------------------------------------------------------------ persistence
    def _persist(self, drives: Iterable[NvmeHealthRecord]) -> None:
        # Skip if we already have a record from today for each drive.
        today = dt.date.today().isoformat()
        try:
            existing_today = set()
            if self._path.exists():
                for line in self._path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    rec_day = dt.datetime.fromtimestamp(rec.get("ts", 0)).date().isoformat()
                    if rec_day == today:
                        existing_today.add(rec.get("device"))
            with self._path.open("a", encoding="utf-8") as fh:
                for d in drives:
                    if d.device in existing_today:
                        continue
                    fh.write(json.dumps(asdict(d)) + "\n")
        except Exception:
            log.exception("Failed to persist SSD health record")
