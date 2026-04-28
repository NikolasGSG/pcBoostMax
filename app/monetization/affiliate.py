"""Affiliate link registry — partner CTAs surfaced in insight cards.

Design rules:
1. Every link is **disclosed** as an affiliate link in the UI.
2. Links open in the user's default browser, never inside the app.
3. The registry is data; no network requests happen here.
4. ``affiliate_links_enabled=False`` in :class:`AppConfig` removes every
   link site-wide.

Add new partners by appending to :func:`default_registry`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class AffiliateLink:
    """A single partner CTA."""
    id: str                # short identifier ('nordvpn', 'crucial-ssd', …)
    label: str             # button text the user sees
    url: str               # tracked URL with our affiliate id baked in
    partner: str           # human-readable partner name
    payout_hint: str = ""  # rough $/conversion — for our planning, never shown
    category: str = "misc" # 'driver' | 'vpn' | 'hardware' | 'software' | 'misc'


class AffiliateRegistry:
    """Lookup table indexed by id and category. In-memory only."""

    def __init__(self, links: Optional[Iterable[AffiliateLink]] = None) -> None:
        self._by_id: Dict[str, AffiliateLink] = {}
        self._by_category: Dict[str, List[AffiliateLink]] = {}
        for lnk in links or []:
            self.add(lnk)

    def add(self, lnk: AffiliateLink) -> None:
        self._by_id[lnk.id] = lnk
        self._by_category.setdefault(lnk.category, []).append(lnk)

    def get(self, link_id: str) -> Optional[AffiliateLink]:
        return self._by_id.get(link_id)

    def by_category(self, category: str) -> List[AffiliateLink]:
        return list(self._by_category.get(category, []))

    def __iter__(self):
        return iter(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)


def default_registry() -> AffiliateRegistry:
    """Built-in partners shipped with GameBoost.

    Active programmes:
      * Amazon Associates  (tag=ngsgsoftworks-20)

    Pending programmes (kept here as commented templates so they can be
    enabled by replacing the placeholder ID and uncommenting):
      * Awin           — for Razer / Corsair / MSI etc. once approved
      * Impact / CJ    — for VPN partners (NordVPN, Surfshark)
      * IObit Direct   — for Driver Booster
    """
    return AffiliateRegistry([
        # --- Hardware (Amazon Associates — active) ----------------------
        AffiliateLink(
            id="samsung-990-pro",
            label="Upgrade to Samsung 990 Pro NVMe",
            url="https://www.amazon.com/dp/B0BHJJ9Y77/?tag=ngsgsoftworks-20",
            partner="Amazon Associates",
            payout_hint="1-4% AOV",
            category="hardware",
        ),
        AffiliateLink(
            id="crucial-ddr5-32gb",
            label="32GB DDR5 RAM kit",
            url="https://www.amazon.com/dp/B0B7B7N5G2/?tag=ngsgsoftworks-20",
            partner="Amazon Associates",
            payout_hint="1-4% AOV",
            category="hardware",
        ),
        AffiliateLink(
            id="thermal-grizzly-paste",
            label="Thermal Grizzly paste — 1.5g",
            url="https://www.amazon.com/dp/B07GZHL7BR/?tag=ngsgsoftworks-20",
            partner="Amazon Associates",
            payout_hint="1-4% AOV",
            category="hardware",
        ),
        AffiliateLink(
            id="logitech-g502-x",
            label="Logitech G502 X — gaming mouse",
            url="https://www.amazon.com/dp/B0B7Y6S58K/?tag=ngsgsoftworks-20",
            partner="Amazon Associates",
            payout_hint="1-4% AOV",
            category="hardware",
        ),
        AffiliateLink(
            id="seasonic-focus-gx-850",
            label="Seasonic Focus GX-850 PSU — 80+ Gold",
            url="https://www.amazon.com/dp/B07F3PMP2W/?tag=ngsgsoftworks-20",
            partner="Amazon Associates",
            payout_hint="1-4% AOV",
            category="hardware",
        ),
        AffiliateLink(
            id="noctua-nh-d15",
            label="Noctua NH-D15 — silent CPU cooler",
            url="https://www.amazon.com/dp/B00L7UZMAK/?tag=ngsgsoftworks-20",
            partner="Amazon Associates",
            payout_hint="1-4% AOV",
            category="hardware",
        ),
        # ----------------------------------------------------------------
        # PENDING PROGRAMMES — enable when approval lands.
        # Replace the placeholder, then uncomment the AffiliateLink(...).
        # ----------------------------------------------------------------
        # AffiliateLink(
        #     id="razer-blackwidow",
        #     label="Razer BlackWidow V4 — gaming keyboard",
        #     url="https://www.awin1.com/cread.php?awinmid=AWIN_MID&awinaffid=AWIN_AFFID&clickref=&ued=https%3A%2F%2Fwww.razer.com%2Fgaming-keyboards%2Frazer-blackwidow-v4",
        #     partner="Razer (via Awin)",
        #     payout_hint="4-10% AOV",
        #     category="hardware",
        # ),
        # AffiliateLink(
        #     id="nordvpn",
        #     label="Lower your ping with NordVPN",
        #     url="https://go.nordvpn.net/aff_c?offer_id=15&aff_id=YOUR_IMPACT_AFFID&url_id=902",
        #     partner="NordVPN (via Impact)",
        #     payout_hint="$40-80 per signup",
        #     category="vpn",
        # ),
        # AffiliateLink(
        #     id="driver-booster",
        #     label="Update drivers automatically",
        #     url="https://www.iobit.com/en/driver-booster.php?ref=YOUR_IOBIT_AFFID",
        #     partner="IObit Driver Booster",
        #     payout_hint="$2 per install",
        #     category="driver",
        # ),
    ])
