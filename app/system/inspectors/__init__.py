"""Hardware inspectors — read-only diagnostic services.

Each inspector returns a list of :class:`Finding` records. Findings are
consumed by:

* the Live Insights panel (priority + sponsored card slots)
* the dedicated views (Driver Auditor, Memory tab, etc.)
* the Auto-Troubleshooter wizard (symptom → finding chain)

Inspectors **never** mutate the system. Use the optimization rules for
that.
"""
from .base import Finding, FindingSeverity, Inspector
from .driver_auditor import DriverAuditor, DriverInfo
from .nvme_health import NvmeHealthInspector, NvmeHealthRecord
from .pcie_link import PcieLinkInspector, PcieLinkInfo
from .ram_xmp import RamXmpInspector, RamModuleInfo

__all__ = [
    "DriverAuditor",
    "DriverInfo",
    "Finding",
    "FindingSeverity",
    "Inspector",
    "NvmeHealthInspector",
    "NvmeHealthRecord",
    "PcieLinkInspector",
    "PcieLinkInfo",
    "RamModuleInfo",
    "RamXmpInspector",
]
