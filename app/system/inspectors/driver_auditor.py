"""Audit installed device drivers — version, age, vendor.

We **do not** auto-update drivers. We just enumerate them and flag the
ones the user typically cares about (GPU, network, audio, storage, USB
controller). The Driver Auditor view groups results, links to vendor
download pages, and surfaces a sponsored "auto-update" partner card
in the empty state.

Source: ``Win32_PnPSignedDriver`` via PowerShell. Every entry has a
``DriverDate``; we treat anything older than 18 months as "old".
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from .base import Finding, FindingSeverity, Inspector, run_powershell

# Vendor → known download page (used to populate "Update" buttons in UI).
VENDOR_DOWNLOAD_URLS: Dict[str, str] = {
    "nvidia": "https://www.nvidia.com/Download/index.aspx",
    "advanced micro devices": "https://www.amd.com/en/support",
    "amd": "https://www.amd.com/en/support",
    "intel": "https://www.intel.com/content/www/us/en/download-center/home.html",
    "realtek": "https://www.realtek.com/en/component/zoo/category/network-interface-controllers-10-100-1000m-gigabit-ethernet-pci-express-software",
    "broadcom": "https://www.broadcom.com/support/download-search",
    "qualcomm": "https://www.qualcomm.com/support",
    "killer": "https://www.intel.com/content/www/us/en/support/products/189925/wireless.html",
    "logitech": "https://support.logi.com/hc/en-us",
    "razer": "https://www.razer.com/support",
}

# Categories we care about (keys are class GUIDs from Windows).
RELEVANT_CLASSES = {
    "Display":         "GPU",
    "Net":             "Network",
    "MEDIA":           "Audio",
    "DiskDrive":       "Storage",
    "USB":             "USB",
    "SCSIAdapter":     "Storage Controller",
    "System":          "Chipset",
    "Bluetooth":       "Bluetooth",
}

OLD_AGE_DAYS = 540   # ~18 months


@dataclass
class DriverInfo:
    device_name: str = ""
    vendor: str = ""
    driver_version: str = ""
    driver_date: str = ""        # YYYY-MM-DD
    category: str = ""           # mapped class
    location: str = ""           # filesystem path of the .sys file
    age_days: int = 0
    download_url: str = ""

    @property
    def is_old(self) -> bool:
        return self.age_days > OLD_AGE_DAYS


@dataclass
class DriverAuditReport:
    drivers: List[DriverInfo] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)

    def by_category(self) -> Dict[str, List[DriverInfo]]:
        grouped: Dict[str, List[DriverInfo]] = {}
        for d in self.drivers:
            grouped.setdefault(d.category or "Other", []).append(d)
        return grouped

    def old_count(self) -> int:
        return sum(1 for d in self.drivers if d.is_old)


class DriverAuditor(Inspector):
    id = "drivers.audit"

    def inspect(self) -> List[Finding]:
        return self.report().findings

    def report(self) -> DriverAuditReport:
        rep = DriverAuditReport()
        rep.drivers = self._read_drivers()
        old = [d for d in rep.drivers if d.is_old]
        if old:
            cats = sorted({d.category for d in old if d.category})
            cat_str = ", ".join(cats) if cats else "device"
            rep.findings.append(Finding(
                id="drivers.outdated",
                severity=FindingSeverity.SUGGESTION,
                title=f"{len(old)} drivers are over 18 months old",
                detail=(
                    f"Older drivers ({cat_str}) often have known performance and "
                    f"stability fixes addressed in newer releases. We don't update "
                    f"them automatically — open the Driver Auditor for vendor links."
                ),
                fix_hint="Open the Driver Auditor view to update each driver from its vendor.",
                sponsored_link_id="driver-booster",
                evidence={"count": len(old), "categories": cats},
            ))
        return rep

    # ------------------------------------------------------------------ readers
    def _read_drivers(self) -> List[DriverInfo]:
        ps = (
            "Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceClass } "
            "| Select-Object DeviceName, Manufacturer, DriverVersion, DriverDate, "
            "DeviceClass, Location | ConvertTo-Json -Depth 2 -Compress"
        )
        raw = run_powershell(ps, timeout=20)
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            data = [data]

        today = dt.date.today()
        out: List[DriverInfo] = []
        seen_keys: set = set()
        for entry in data:
            cls = str(entry.get("DeviceClass") or "")
            cat = RELEVANT_CLASSES.get(cls)
            if cat is None:
                continue   # skip uninteresting categories
            name = (str(entry.get("DeviceName") or "")).strip()
            ver = (str(entry.get("DriverVersion") or "")).strip()
            vendor = (str(entry.get("Manufacturer") or "")).strip()

            # Dedupe — Windows enumerates duplicates per device-instance.
            key = (name, ver)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            date_str = self._parse_driver_date(entry.get("DriverDate"))
            age = self._age_days(date_str, today) if date_str else 0
            url = VENDOR_DOWNLOAD_URLS.get(vendor.lower(), "")
            out.append(DriverInfo(
                device_name=name,
                vendor=vendor,
                driver_version=ver,
                driver_date=date_str,
                category=cat,
                location=(str(entry.get("Location") or "")).strip(),
                age_days=age,
                download_url=url,
            ))
        return sorted(out, key=lambda d: (d.category, d.device_name.lower()))

    @staticmethod
    def _parse_driver_date(value) -> str:
        if not value:
            return ""
        if isinstance(value, str):
            # PowerShell ConvertTo-Json emits CIM_DATETIME as
            # "/Date(<ms>+TZ)/" — extract the ms.
            m = re.search(r"\((-?\d+)", value)
            if m:
                ms = int(m.group(1))
                try:
                    return dt.datetime.fromtimestamp(ms / 1000).date().isoformat()
                except (OSError, OverflowError, ValueError):
                    return ""
            try:
                return dt.datetime.fromisoformat(value.split("T")[0]).date().isoformat()
            except ValueError:
                return ""
        return ""

    @staticmethod
    def _age_days(date_str: str, today: dt.date) -> int:
        try:
            d = dt.date.fromisoformat(date_str)
            return max(0, (today - d).days)
        except ValueError:
            return 0
