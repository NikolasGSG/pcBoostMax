"""Base class for every optimization rule.

Each rule answers four questions:
    1. Does this machine need it?                 ``evaluate()``
    2. What does it actually do, and why?         class-level metadata
    3. What's the risk?                           class-level metadata
    4. Can I undo it?                             ``reversible`` + capture/apply/restore

A rule is purely declarative + three small methods. The engine never
inspects private state.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ...core.constants import IMPACT_MINOR, RISK_SAFE
from ...system.hardware_detector import HardwareSnapshot


@dataclass
class RuleEvaluation:
    """Result of a rule evaluating itself against the current system."""

    applicable: bool
    reason: str = ""
    score: int = 0                    # 0..100, estimated potential gain
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleOutcome:
    """Result of applying a rule."""

    ok: bool
    message: str = ""
    backup_payload: Optional[Dict[str, Any]] = None   # None if nothing to restore


class OptimizationRule(ABC):
    """Abstract rule. Subclass, fill in metadata + the three hooks."""

    # -- metadata (override per rule) ---------------------------------------
    id: str = "base"
    title: str = "Unnamed optimization"
    category: str = "general"         # "startup" | "cleanup" | "power" | "services" | "visual"
    what: str = ""                    # one-paragraph plain-English description
    why: str = ""                     # why it matters for gaming
    risk: str = RISK_SAFE             # one of core.constants.RISK_*
    impact: str = IMPACT_MINOR        # one of core.constants.IMPACT_*
    reversible: bool = True
    requires_admin: bool = False
    advisory: bool = False            # True ⇒ rule only reports / guides; no state change
                                      #       ⇒ engine skips post-apply verification.

    # -- lifecycle ----------------------------------------------------------
    @abstractmethod
    def evaluate(self, hardware: HardwareSnapshot) -> RuleEvaluation:
        """Decide whether this machine would benefit. Must be pure / read-only."""

    @abstractmethod
    def apply(self) -> RuleOutcome:
        """Perform the change. Return a backup payload for later rollback."""

    @abstractmethod
    def restore(self, payload: Dict[str, Any]) -> None:
        """Reverse the change using the payload returned by :meth:`apply`."""

    # -- helpers ------------------------------------------------------------
    def describe(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "what": self.what,
            "why": self.why,
            "risk": self.risk,
            "impact": self.impact,
            "reversible": self.reversible,
            "requires_admin": self.requires_admin,
        }
