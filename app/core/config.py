"""Persistent user configuration.

Stored as JSON in ``%LOCALAPPDATA%/GameBoostOptimizer/config.json``.
We keep the schema intentionally tiny — the heavy profile data lives in
``profiles/``.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from typing import Any

from ..utils.logger import get_logger
from ..utils.paths import CONFIG_FILE, ensure_app_dirs
from .constants import MODE_SAFE

log = get_logger("core.config")


@dataclass
class AppConfig:
    mode: str = MODE_SAFE                     # "safe" | "advanced"
    create_restore_point: bool = True         # before applying an optimization plan
    auto_backup: bool = True                  # mirror settings into backups/
    confirm_cleanup: bool = True              # always show files-to-delete preview
    enable_animations: bool = True
    active_profile: str = "Balanced"
    accepted_disclaimer: bool = False
    window_geometry: dict[str, int] = field(default_factory=dict)

    # -- Overlay (HUD) --
    overlay_enabled: bool = False
    overlay_position: str = "top-right"       # top-left | top-right | bottom-left | bottom-right
    overlay_opacity: int = 85                 # 40..100
    overlay_click_through: bool = True
    overlay_show_fps: bool = True
    overlay_show_cpu: bool = True
    overlay_show_gpu: bool = True
    overlay_show_ram: bool = True
    overlay_show_net: bool = True
    overlay_show_disk: bool = False
    overlay_show_frametime: bool = True
    overlay_show_process: bool = True
    overlay_compact: bool = False
    overlay_hotkey_ctrl: bool = True
    overlay_hotkey_shift: bool = True
    overlay_hotkey_alt: bool = False
    overlay_hotkey_key: str = "F12"
    overlay_auto_show_game: bool = False      # auto-show when a fullscreen game is detected

    # -- Tray / Game auto-detect --
    minimize_to_tray: bool = True             # [X] → hide to tray instead of quit
    auto_game_mode: bool = False              # auto-enable Game Mode on fullscreen game
    auto_hud_on_game: bool = False            # auto-show HUD when a game starts

    # -- AutoPilot (v2 hands-free automation) --
    autopilot_enabled: bool = False           # master switch
    autopilot_apply_recommended: bool = True  # silent-apply Recommended preset on boot
    autopilot_per_game_profiles: bool = True  # apply per-game profile when game launches
    autopilot_act_on_insights: bool = True    # auto-resolve safe critical insights
    autopilot_first_run_complete: bool = False  # has the welcome offered AutoPilot

    # -- Monetization (ads-only, app is fully free) --
    ads_enabled: bool = True                  # master switch: show in-app banners + sponsor link
    ads_consent_given: bool = False           # has the first-run consent dialog been shown
    personalized_ads: bool = False            # GDPR/CCPA — opt-in for personalized targeting
    sponsored_cards_enabled: bool = True      # show sponsored partner cards in Live Insights
    telemetry_opt_in: bool = False            # anonymous DAU/CTR ping (opt-in only)
    # URL of the JSON ad manifest. House ads + affiliate creatives. Override
    # per build (or in config.json) to point at your own static host.
    # NOTE: baked at https://NikolasGSG.github.io/pcBoostMax/ — change
    # only if forking under a different GitHub user/repo.
    ads_manifest_url: str = "https://NikolasGSG.github.io/pcBoostMax/ads/manifest.json"
    # URL of the hosted sponsor page (where AdSense + Microsoft Ads run).
    # Opened in the system browser when the user clicks "Get deals".
    ads_sponsor_url: str = "https://NikolasGSG.github.io/pcBoostMax/sponsor/"

    # -- Cosmetic / theme (v2.1) --
    theme_preset: str = "apex"                # see app/ui/theme/presets.py

    # ---------------------------------------------------------------- IO
    @classmethod
    def load(cls) -> "AppConfig":
        ensure_app_dirs()
        if not CONFIG_FILE.exists():
            cfg = cls()
            cfg.save()
            return cfg
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            log.warning("Config file unreadable, resetting to defaults")
            cfg = cls()
            cfg.save()
            return cfg
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in valid})

    def save(self) -> None:
        ensure_app_dirs()
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def update(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.save()
