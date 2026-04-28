"""Detect RAM running below its rated XMP/EXPO speed.

The user's *current* memory speed comes from ``Win32_PhysicalMemory.Speed``.
The *rated* (SPD) speed isn't directly exposed; we use a couple of
heuristics:

1. ``ConfiguredClockSpeed`` (current) vs ``Speed`` (negotiated max) on
   modern Windows. If rated > current, XMP is likely off.
2. Heuristic gap detection: a kit branded as 3200/3600/4800/6000 will
   round to common boundaries; if the current speed is well below those
   bands we flag it.

This is **best-effort** — Windows doesn't expose every SPD field, and
many machines truthfully report current = rated. We only emit a warning
when we have a confident gap.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional

from .base import Finding, FindingSeverity, Inspector, run_powershell

# Common XMP/EXPO marketed speeds. If current speed is far below the next
# tier up, we suggest enabling XMP.
_DDR4_TIERS = [2133, 2400, 2666, 2933, 3000, 3200, 3600, 4000, 4400]
_DDR5_TIERS = [4800, 5200, 5600, 6000, 6400, 7200, 7800, 8000]


@dataclass
class RamModuleInfo:
    slot: str = ""
    capacity_gb: float = 0.0
    current_mhz: int = 0
    rated_mhz: int = 0
    manufacturer: str = ""
    part_number: str = ""
    is_ddr5: bool = False


@dataclass
class RamXmpReport:
    modules: List[RamModuleInfo] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)


class RamXmpInspector(Inspector):
    id = "ram.xmp"

    def inspect(self) -> List[Finding]:
        return self.report().findings

    def report(self) -> RamXmpReport:
        rep = RamXmpReport()
        modules = self._read_modules()
        rep.modules = modules
        if not modules:
            return rep

        # Aggregate finding: lowest-running stick wins.
        slowest = min(modules, key=lambda m: m.current_mhz or 999_999)
        if slowest.current_mhz <= 0:
            return rep

        is_ddr5 = any(m.is_ddr5 for m in modules)
        tiers = _DDR5_TIERS if is_ddr5 else _DDR4_TIERS

        # If we have a hard rated speed, trust it; else infer from tiers.
        target = slowest.rated_mhz if slowest.rated_mhz > slowest.current_mhz else self._next_tier(slowest.current_mhz, tiers)

        if target and target > slowest.current_mhz * 1.10:
            pct = ((target - slowest.current_mhz) / slowest.current_mhz) * 100
            rep.findings.append(Finding(
                id="ram.xmp_off",
                severity=FindingSeverity.WARNING,
                title=f"RAM running {pct:.0f}% slower than rated",
                detail=(
                    f"Your memory is running at {slowest.current_mhz} MHz but appears "
                    f"to support {target} MHz. Enabling XMP / EXPO in your BIOS would "
                    f"unlock the full speed without overclocking."
                ),
                fix_hint="Reboot → enter BIOS/UEFI → enable XMP or EXPO → save & exit.",
                evidence={
                    "current_mhz": slowest.current_mhz,
                    "rated_mhz": target,
                    "module_count": len(modules),
                    "is_ddr5": is_ddr5,
                    "manufacturer": slowest.manufacturer,
                    "part_number": slowest.part_number,
                },
            ))

        return rep

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _next_tier(current: int, tiers: List[int]) -> int:
        """Pick the next-higher rated tier above the current speed.
        Returns 0 if current is already at/above the highest known tier
        (i.e. nothing to flag)."""
        for t in tiers:
            if t > current * 1.05:
                return t
        return 0

    def _read_modules(self) -> List[RamModuleInfo]:
        ps = (
            "Get-CimInstance Win32_PhysicalMemory | Select-Object "
            "DeviceLocator, Capacity, Speed, ConfiguredClockSpeed, Manufacturer, "
            "PartNumber, SMBIOSMemoryType | ConvertTo-Json -Depth 2 -Compress"
        )
        raw = run_powershell(ps)
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            data = [data]
        modules: List[RamModuleInfo] = []
        for entry in data:
            try:
                cap_b = int(entry.get("Capacity") or 0)
                speed = int(entry.get("Speed") or 0)        # rated/max negotiated
                cur = int(entry.get("ConfiguredClockSpeed") or 0)  # actual running
                # SMBIOSMemoryType: 26 = DDR4, 34 = DDR5 (per SMBIOS 3.5+)
                mem_type = int(entry.get("SMBIOSMemoryType") or 0)
                modules.append(RamModuleInfo(
                    slot=str(entry.get("DeviceLocator", "")),
                    capacity_gb=cap_b / (1024 ** 3),
                    current_mhz=cur or speed,
                    rated_mhz=speed,
                    manufacturer=str(entry.get("Manufacturer", "")).strip(),
                    part_number=str(entry.get("PartNumber", "")).strip(),
                    is_ddr5=mem_type == 34,
                ))
            except (TypeError, ValueError):
                continue
        return modules
