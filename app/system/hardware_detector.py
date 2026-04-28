"""Identify the machine: CPU, GPU, RAM, disks, OS.

``psutil`` does the heavy lifting cross-platform; on Windows we additionally
try WMI for GPU / motherboard. Every detector is wrapped in ``try/except`` so
an unusual machine never crashes us — we just report "Unknown".
"""
from __future__ import annotations

import platform
import sys
from dataclasses import dataclass, field
from typing import List, Optional

import psutil

from ..utils.logger import get_logger

log = get_logger("system.hardware")


# ----------------------------------------------------------------------------- models
@dataclass
class CPUInfo:
    name: str = "Unknown CPU"
    vendor: str = ""
    cores_physical: int = 0
    cores_logical: int = 0
    base_mhz: float = 0.0
    max_mhz: float = 0.0
    architecture: str = ""


@dataclass
class GPUInfo:
    name: str = "Unknown GPU"
    vram_mb: int = 0
    driver_version: str = ""


@dataclass
class RAMInfo:
    total_bytes: int = 0
    modules: int = 0
    speed_mhz: int = 0
    form_factor: str = ""


@dataclass
class DiskInfo:
    device: str
    mountpoint: str
    fstype: str
    total_bytes: int
    free_bytes: int
    is_ssd: Optional[bool] = None


@dataclass
class OSInfo:
    system: str = ""
    release: str = ""
    version: str = ""
    build: str = ""
    hostname: str = ""


@dataclass
class HardwareSnapshot:
    cpu: CPUInfo = field(default_factory=CPUInfo)
    gpus: List[GPUInfo] = field(default_factory=list)
    ram: RAMInfo = field(default_factory=RAMInfo)
    disks: List[DiskInfo] = field(default_factory=list)
    os: OSInfo = field(default_factory=OSInfo)
    has_battery: bool = False          # True ⇒ laptop (or UPS-attached)
    is_laptop: bool = False            # stricter heuristic — battery + no mains dependency

    @property
    def primary_gpu(self) -> GPUInfo:
        return self.gpus[0] if self.gpus else GPUInfo()


# ----------------------------------------------------------------------------- detector
class HardwareDetector:
    """One-shot detector. Safe to call multiple times but cached per instance."""

    def __init__(self) -> None:
        self._cached: Optional[HardwareSnapshot] = None

    def detect(self, force: bool = False) -> HardwareSnapshot:
        if self._cached and not force:
            return self._cached
        has_battery, is_laptop = self._battery()
        snap = HardwareSnapshot(
            cpu=self._cpu(),
            gpus=self._gpus(),
            ram=self._ram(),
            disks=self._disks(),
            os=self._os(),
            has_battery=has_battery,
            is_laptop=is_laptop,
        )
        self._cached = snap
        log.info(
            "Hardware detected: %s / %d GB RAM / %s",
            snap.cpu.name,
            snap.ram.total_bytes // (1024 ** 3) if snap.ram.total_bytes else 0,
            snap.primary_gpu.name,
        )
        return snap

    # ------------------------------------------------------------------ CPU
    def _cpu(self) -> CPUInfo:
        info = CPUInfo()
        info.cores_physical = psutil.cpu_count(logical=False) or 0
        info.cores_logical = psutil.cpu_count(logical=True) or 0
        info.architecture = platform.machine()
        freq = psutil.cpu_freq()
        if freq:
            info.base_mhz = float(getattr(freq, "min", 0) or 0)
            info.max_mhz = float(getattr(freq, "max", 0) or 0)

        info.name = platform.processor() or platform.machine() or "Unknown CPU"
        if sys.platform == "win32":
            try:
                import wmi  # type: ignore

                c = wmi.WMI()
                for proc in c.Win32_Processor():
                    if proc.Name:
                        info.name = proc.Name.strip()
                    if proc.Manufacturer:
                        info.vendor = proc.Manufacturer.strip()
                    if proc.MaxClockSpeed:
                        info.max_mhz = float(proc.MaxClockSpeed)
                    break
            except Exception:
                log.debug("WMI CPU probe failed", exc_info=True)
        return info

    # ------------------------------------------------------------------ GPU
    def _gpus(self) -> List[GPUInfo]:
        gpus: List[GPUInfo] = []
        if sys.platform == "win32":
            try:
                import wmi  # type: ignore

                c = wmi.WMI()
                for adapter in c.Win32_VideoController():
                    name = (adapter.Name or "").strip() or "Unknown GPU"
                    vram = int(adapter.AdapterRAM or 0) // (1024 * 1024) if adapter.AdapterRAM else 0
                    driver = (adapter.DriverVersion or "").strip()
                    gpus.append(GPUInfo(name=name, vram_mb=vram, driver_version=driver))
            except Exception:
                log.debug("WMI GPU probe failed", exc_info=True)
        if not gpus:
            gpus.append(GPUInfo(name="Integrated / Unknown"))
        return gpus

    # ------------------------------------------------------------------ RAM
    def _ram(self) -> RAMInfo:
        vm = psutil.virtual_memory()
        info = RAMInfo(total_bytes=vm.total)
        if sys.platform == "win32":
            try:
                import wmi  # type: ignore

                c = wmi.WMI()
                modules = list(c.Win32_PhysicalMemory())
                info.modules = len(modules)
                speeds = [int(m.Speed) for m in modules if m.Speed]
                if speeds:
                    info.speed_mhz = max(speeds)
                if modules and modules[0].FormFactor is not None:
                    info.form_factor = str(modules[0].FormFactor)
            except Exception:
                log.debug("WMI RAM probe failed", exc_info=True)
        return info

    # ------------------------------------------------------------------ Disks
    def _disks(self) -> List[DiskInfo]:
        disks: List[DiskInfo] = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except Exception:
                continue
            disks.append(
                DiskInfo(
                    device=part.device,
                    mountpoint=part.mountpoint,
                    fstype=part.fstype,
                    total_bytes=usage.total,
                    free_bytes=usage.free,
                    is_ssd=None,  # reliably detecting SSD vs HDD needs admin; we skip
                )
            )
        return disks

    # ------------------------------------------------------------------ OS
    def _os(self) -> OSInfo:
        return OSInfo(
            system=platform.system(),
            release=platform.release(),
            version=platform.version(),
            build=platform.version().split(".")[-1] if "." in platform.version() else "",
            hostname=platform.node(),
        )

    # ------------------------------------------------------------------ Battery / chassis
    def _battery(self) -> tuple[bool, bool]:
        """Return (has_battery, is_laptop).

        ``has_battery`` is True whenever psutil/WMI finds a battery. ``is_laptop``
        additionally checks the ChassisTypes code via WMI on Windows so a
        desktop-with-UPS doesn't get classified as a laptop.
        """
        has_battery = False
        try:
            batt = psutil.sensors_battery()
            if batt is not None:
                has_battery = True
        except Exception:
            pass

        is_laptop = has_battery  # sensible default
        if sys.platform == "win32":
            try:
                import wmi  # type: ignore

                c = wmi.WMI()
                laptop_types = {8, 9, 10, 11, 12, 14, 18, 21, 30, 31, 32}
                for chassis in c.Win32_SystemEnclosure():
                    for t in (chassis.ChassisTypes or []):
                        if int(t) in laptop_types:
                            is_laptop = True
                            break
            except Exception:
                log.debug("WMI chassis probe failed", exc_info=True)
        return has_battery, is_laptop
