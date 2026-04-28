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
    """Built-in partners. Replace the URLs with your real tracked ones.

    All URLs use placeholder query params that you should swap with your
    real partner ids before shipping.
    """
    return AffiliateRegistry([
        # --- Drivers / system utilities ---
        AffiliateLink(
            id="driver-booster",
            label="Update drivers automatically",
            url="https://www.iobit.com/en/driver-booster.php?ref=YOUR_AFFILIATE_ID",
            partner="IObit Driver Booster",
            payout_hint="$2 per install",
            category="driver",
        ),
        # --- VPN / network ---
        AffiliateLink(
            id="nordvpn",
            label="Lower your ping with NordVPN",
            url="https://nordvpn.com/?utm_medium=affiliate&utm_term=YOUR_REF",
            partner="NordVPN",
            payout_hint="$40-80 per signup",
            category="vpn",
        ),
        AffiliateLink(
            id="cloudflare-warp",
            label="Try Cloudflare WARP (free)",
            url="https://1.1.1.1/?ref=YOUR_REF",
            partner="Cloudflare WARP",
            payout_hint="brand awareness",
            category="vpn",
        ),
        # --- Hardware ---
        AffiliateLink(
            id="samsung-990-pro",
            label="Upgrade to Samsung 990 Pro NVMe",
            url="https://www.amazon.com/dp/B0BHJJ9Y77/?tag=YOUR_TAG",
            partner="Amazon Associates",
            payout_hint="1-4% AOV",
            category="hardware",
        ),
        AffiliateLink(
            id="crucial-ddr5-32gb",
            label="32GB DDR5 RAM kit",
            url="https://www.amazon.com/dp/B0B7B7N5G2/?tag=YOUR_TAG",
            partner="Amazon Associates",
            payout_hint="1-4% AOV",
            category="hardware",
        ),
        AffiliateLink(
            id="thermal-grizzly-paste",
            label="Thermal Grizzly paste — 1.5g",
            url="https://www.amazon.com/dp/B07GZHL7BR/?tag=YOUR_TAG",
            partner="Amazon Associates",
            payout_hint="1-4% AOV",
            category="hardware",
        ),
    ])
