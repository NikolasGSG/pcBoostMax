"""Monetization package — ads-supported, app is fully free.

Three components:

* :mod:`ad_banner` — native Qt banner widget shown on Dashboard / Game
  Hub. Renders a creative pulled from a JSON manifest we host. Click
  opens the user's default browser at a UTM-tagged sponsor URL where
  AdSense + Microsoft Ads can run **legitimately** (the desktop app is
  the traffic source, not the ad-serving surface).
* :mod:`house_ads` — JSON manifest fetcher with on-disk cache + bundled
  fallbacks. Pure stdlib, runs on a background thread.
* :mod:`affiliate` — registry of partner CTAs surfaced inside Live
  Insights as native sponsored cards.

Master switch: ``AppConfig.ads_enabled``. When false, every component
above self-hides and makes zero network calls.
"""
from .ad_banner import AdBanner
from .affiliate import AffiliateLink, AffiliateRegistry, default_registry
from .house_ads import Creative, Manifest, build_click_url, fetch as fetch_manifest

__all__ = [
    "AdBanner",
    "AffiliateLink",
    "AffiliateRegistry",
    "Creative",
    "Manifest",
    "build_click_url",
    "default_registry",
    "fetch_manifest",
]
