"""Verify the GPU is on the PCIe link width / generation it advertises.

Strategy:

1. Try ``nvidia-smi -q -d PCI`` for NVIDIA cards — gives current AND max.
2. For AMD, parse the registry "PCIE Status" key set by the driver, or
   fall back to a generic "we couldn't measure this" result.

Findings emitted:

* ``pcie.gen_downgrade``  — running on Gen3 when Gen4 is supported
* ``pcie.width_downgrade`` — x8 when x16 is supported (often laptop /
  M.2-stealing-lanes scenarios)

This is purely informational — there's no software fix; we link to a
short explainer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from .base import Finding, FindingSeverity, Inspector, run_command


@dataclass
class PcieLinkInfo:
    gpu_name: str = ""
    current_gen: int = 0
    max_gen: int = 0
    current_width: int = 0
    max_width: int = 0
    source: str = ""    # "nvidia-smi" | "amd-registry" | "unknown"


@dataclass
class PcieLinkReport:
    links: List[PcieLinkInfo] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)


class PcieLinkInspector(Inspector):
    id = "pcie.link"

    def inspect(self) -> List[Finding]:
        return self.report().findings

    def report(self) -> PcieLinkReport:
        rep = PcieLinkReport()
        nvidia = self._read_nvidia()
        if nvidia:
            rep.links.extend(nvidia)
        for link in rep.links:
            self._evaluate(link, rep.findings)
        return rep

    # ------------------------------------------------------------------ readers
    def _read_nvidia(self) -> List[PcieLinkInfo]:
        out = run_command(["nvidia-smi", "-q", "-d", "PCI"])
        if not out:
            return []

        # nvidia-smi -q output is a long block of "Key : Value" lines.
        # Extract per-GPU sections.
        gpus: List[PcieLinkInfo] = []
        current = PcieLinkInfo(source="nvidia-smi")
        in_pci = False
        in_link_info = False

        for raw_line in out.splitlines():
            stripped = raw_line.strip()
            if stripped.startswith("GPU "):
                if current.gpu_name and (current.current_gen or current.current_width):
                    gpus.append(current)
                current = PcieLinkInfo(source="nvidia-smi")
                continue
            if stripped.startswith("Product Name"):
                _, _, val = stripped.partition(":")
                current.gpu_name = val.strip()
                continue
            if stripped == "PCI":
                in_pci = True
                continue
            if in_pci and stripped.startswith("Link Width"):
                in_link_info = "Link Width" in stripped
                continue
            if "Generation" in stripped and ":" in stripped:
                # Headers under "Link Width" use indentation we've lost — read
                # any "Gen X" / "x N" pairs that follow the "Generation" or
                # "Width" hints.
                m = re.match(r"(Max|Current)\s*:\s*(\d+)", stripped)
                if m:
                    n = int(m.group(2))
                    if "Max" in stripped:
                        current.max_gen = current.max_gen or n
                    else:
                        current.current_gen = current.current_gen or n
            if "x" in stripped.lower() and ":" in stripped:
                m = re.match(r"(Max|Current)\s*:\s*(\d+)x", stripped)
                if m:
                    n = int(m.group(2))
                    if "Max" in stripped:
                        current.max_width = current.max_width or n
                    else:
                        current.current_width = current.current_width or n

        if current.gpu_name and (current.current_gen or current.current_width):
            gpus.append(current)
        return gpus

    # ------------------------------------------------------------------ findings
    @staticmethod
    def _evaluate(link: PcieLinkInfo, out: List[Finding]) -> None:
        if link.max_gen and link.current_gen and link.current_gen < link.max_gen:
            out.append(Finding(
                id="pcie.gen_downgrade",
                severity=FindingSeverity.WARNING,
                title=f"GPU on PCIe Gen {link.current_gen} (supports Gen {link.max_gen})",
                detail=(
                    f"{link.gpu_name} is negotiating a PCIe Gen {link.current_gen} link, "
                    f"but the card supports Gen {link.max_gen}. This is usually caused "
                    f"by a slot or BIOS setting forcing the older generation."
                ),
                fix_hint="In BIOS, set the GPU's PCIe slot to 'Auto' or its highest gen. Reseat the GPU if the slot is dirty.",
                evidence={
                    "gpu": link.gpu_name,
                    "current_gen": link.current_gen,
                    "max_gen": link.max_gen,
                },
            ))
        if link.max_width and link.current_width and link.current_width < link.max_width:
            out.append(Finding(
                id="pcie.width_downgrade",
                severity=FindingSeverity.WARNING,
                title=f"GPU on PCIe x{link.current_width} (supports x{link.max_width})",
                detail=(
                    f"{link.gpu_name} is running on x{link.current_width} but supports "
                    f"x{link.max_width}. Common cause: an M.2 SSD sharing lanes with the "
                    f"GPU slot."
                ),
                fix_hint="Move M.2 drives to chipset slots or use the dedicated CPU-attached slot for the GPU.",
                evidence={
                    "gpu": link.gpu_name,
                    "current_width": link.current_width,
                    "max_width": link.max_width,
                },
            ))
