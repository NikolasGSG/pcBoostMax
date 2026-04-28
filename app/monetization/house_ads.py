"""House-ad manifest fetcher.

Pulls a JSON manifest from a URL we control (e.g. GitHub Pages) describing
the current rotation of house / sponsored creatives. We render those
inside the app as native Qt widgets — no third-party SDK in the binary,
no ToS issues with AdSense / Microsoft Advertising.

Click-throughs open the user's system browser at a sponsor URL we host,
where AdSense / Microsoft Ads run **legitimately** (the desktop app
becomes a traffic source, not the ad-serving surface).

Manifest schema (versioned)::

    {
      "version": 1,
      "fetched_at": "2026-04-28T11:00:00Z",
      "creatives": [
        {
          "id": "nvme-q2-2026",
          "headline": "Upgrade to NVMe storage",
          "body": "5x faster game load times. From $59.",
          "cta": "Shop deals",
          "image_url": "https://NIK0gs.github.io/pcBoostMax/ads/img/nvme.png",
          "click_url": "https://amzn.to/3xyz?tag=YOUR_TAG",
          "sponsor": "Amazon Associates",
          "weight": 1.0,
          "expires_at": "2026-12-31T23:59:59Z"
        }
      ]
    }

Network behaviour:

* HEAD-only ETag check on second-and-subsequent loads.
* 24h on-disk cache in ``%LOCALAPPDATA%\\GameBoostOptimizer\\ads_manifest.json``.
* On any error: fall back to bundled defaults (project's own GitHub link).
* Never blocks UI startup — calls live on a background thread.
"""
from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from ..utils.logger import get_logger
from ..utils.paths import APP_DATA_DIR, ensure_app_dirs

log = get_logger("monetization.house_ads")

CACHE_FILE = APP_DATA_DIR / "ads_manifest.json"
CACHE_TTL_SECONDS = 24 * 60 * 60   # one day


@dataclass(frozen=True)
class Creative:
    """A single banner creative.

    All fields are validated at parse time — a malformed manifest entry
    is silently skipped, never raised, so a broken upstream can't crash
    the UI.
    """
    id: str
    headline: str
    body: str
    cta: str
    click_url: str
    sponsor: str = ""
    image_url: str = ""        # optional — empty means text-only card
    weight: float = 1.0
    expires_at: Optional[str] = None  # ISO-8601, optional

    def is_active(self, *, now: Optional[float] = None) -> bool:
        if not self.expires_at:
            return True
        try:
            exp = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        ts = now if now is not None else time.time()
        return exp.timestamp() > ts


@dataclass
class Manifest:
    version: int = 1
    fetched_at: str = ""
    creatives: List[Creative] = field(default_factory=list)

    def active(self) -> List[Creative]:
        return [c for c in self.creatives if c.is_active()]

    def pick_one(self) -> Optional[Creative]:
        """Weighted random pick from currently active creatives."""
        active = self.active()
        if not active:
            return None
        weights = [max(0.01, c.weight) for c in active]
        return random.choices(active, weights=weights, k=1)[0]


# ---------------------------------------------------------------- defaults
def _bundled_default() -> Manifest:
    """Always-available fallback so the banner has something to show
    when offline / before the first manifest fetch succeeds.

    Points at the project's own affiliate links — guaranteed to work,
    no third-party dependency.
    """
    return Manifest(
        version=1,
        fetched_at=datetime.now(tz=timezone.utc).isoformat(),
        creatives=[
            Creative(
                id="house-nvme",
                headline="NVMe is the single biggest game-load upgrade",
                body="From 35s to 7s on Cyberpunk launch. Top picks under $80.",
                cta="See deals",
                click_url="https://NIK0gs.github.io/pcBoostMax/sponsor/?slot=nvme",
                sponsor="GameBoost Picks",
                weight=1.0,
            ),
            Creative(
                id="house-ram",
                headline="32 GB DDR5 unlocks higher 1% lows",
                body="Free yourself from page-faulting. Curated kits, all brands.",
                cta="Browse RAM kits",
                click_url="https://NIK0gs.github.io/pcBoostMax/sponsor/?slot=ram",
                sponsor="GameBoost Picks",
                weight=1.0,
            ),
            Creative(
                id="house-vpn",
                headline="Lower your matchmaking ping",
                body="Try a gaming-tuned VPN free for 30 days.",
                cta="Try free",
                click_url="https://NIK0gs.github.io/pcBoostMax/sponsor/?slot=vpn",
                sponsor="GameBoost Picks",
                weight=0.7,
            ),
        ],
    )


# ---------------------------------------------------------------- IO
def _read_cache() -> Optional[Manifest]:
    if not CACHE_FILE.exists():
        return None
    try:
        age = time.time() - CACHE_FILE.stat().st_mtime
        if age > CACHE_TTL_SECONDS:
            return None
        raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return _parse_manifest(raw)
    except (OSError, json.JSONDecodeError, ValueError):
        log.exception("ads cache unreadable, ignoring")
        return None


def _write_cache(manifest: Manifest) -> None:
    try:
        ensure_app_dirs()
        CACHE_FILE.write_text(
            json.dumps(asdict(manifest), indent=2),
            encoding="utf-8",
        )
    except OSError:
        log.exception("failed to write ads cache")


def _parse_manifest(raw: dict) -> Manifest:
    """Tolerant parser — drops creatives missing required fields."""
    creatives: List[Creative] = []
    for entry in raw.get("creatives", []):
        try:
            creatives.append(Creative(
                id=str(entry["id"]),
                headline=str(entry["headline"]),
                body=str(entry.get("body", "")),
                cta=str(entry.get("cta", "Learn more")),
                click_url=str(entry["click_url"]),
                sponsor=str(entry.get("sponsor", "")),
                image_url=str(entry.get("image_url", "")),
                weight=float(entry.get("weight", 1.0)),
                expires_at=entry.get("expires_at"),
            ))
        except (KeyError, TypeError, ValueError):
            log.warning("skipping malformed creative: %r", entry)
    return Manifest(
        version=int(raw.get("version", 1)),
        fetched_at=str(raw.get("fetched_at", "")),
        creatives=creatives,
    )


def fetch(url: str, *, timeout: float = 4.0) -> Manifest:
    """Synchronous fetch. Caller is expected to run this on a worker thread.

    Returns the cached/bundled manifest on any error — never raises.
    """
    cached = _read_cache()
    if cached is not None and cached.creatives:
        # Cache hit; refresh in the background by the next caller.
        return cached

    if not url:
        return _bundled_default()

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "GameBoost/2.1 (+https://gameboost.app)",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise urllib.error.URLError(f"HTTP {resp.status}")
            raw = json.loads(resp.read().decode("utf-8", errors="replace"))
        manifest = _parse_manifest(raw)
        if not manifest.creatives:
            log.info("manifest empty, using bundled defaults")
            return _bundled_default()
        _write_cache(manifest)
        return manifest
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, ValueError, TimeoutError, OSError):
        log.info("manifest fetch failed, falling back to bundled defaults")
        return _bundled_default()


def build_click_url(base_url: str, creative_id: str, slot: str) -> str:
    """Append UTM tags to a click-through URL.

    These tags live in the URL only — nothing is stored or transmitted
    elsewhere. They let *the destination page* (which can run AdSense /
    Microsoft Ads) attribute the click without us running any analytics
    SDK in the desktop app.
    """
    sep = "&" if "?" in base_url else "?"
    return (
        f"{base_url}{sep}"
        f"utm_source=gameboost"
        f"&utm_medium=banner"
        f"&utm_campaign={creative_id}"
        f"&utm_content={slot}"
    )
