"""Apex palette — single source of truth for every colour in GameBoost.

Design intent: a hardware-grade HUD aesthetic in the spirit of Razer
Synapse / Logitech G HUB. Obsidian-black surfaces, hairline rules, and
a tri-tone brand system semantically applied:

* **accent**     – electric LIME primary: status, CTAs, applied state
* **neon_blue**  – CYAN secondary: live telemetry, charts, focus rings
* **violet**     – tertiary: "Elite" features, Game Mode, accents only

The accents are deliberately tuned so a green/cyan glow on near-black
feels engineered rather than cartoonish. ``hex_*`` and ``glow_*`` tokens
drive the custom-painted hex-grid panels and corner brackets.

NB. Token *names* are stable across the v1 → v2 redesign so every
existing widget keeps working — only values changed.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    # -- Surfaces (darkest → lightest) ---------------------------------------
    bg_base:      str = "#06080B"   # window background — true obsidian
    bg_surface:   str = "#0C1014"   # cards
    bg_elevated:  str = "#141A21"   # hover / elevated cards
    bg_sunken:    str = "#03050A"   # graph wells, sunken panels

    # -- Borders / dividers --------------------------------------------------
    border:       str = "#1B232E"
    border_soft:  str = "#10161E"
    border_strong:str = "#2A3340"
    border_hairline: str = "#212B38"   # 1px chrome borders on cards

    # -- Text ----------------------------------------------------------------
    text_primary:   str = "#EAF1FA"
    text_secondary: str = "#7E8C9F"
    text_tertiary:  str = "#4F5A6B"
    text_disabled:  str = "#37404E"
    text_on_accent: str = "#04140A"

    # -- Primary accent (electric LIME) --------------------------------------
    accent:         str = "#A6FF00"
    accent_hover:   str = "#B6FF33"
    accent_pressed: str = "#8DDE00"
    accent_dim:     str = "#1F2A05"   # deep lime wash
    accent_glow:    str = "#D4FF66"   # outer glow rings

    # -- Secondary accent (electric CYAN) ------------------------------------
    neon_blue:      str = "#00E4FF"
    neon_blue_hot:  str = "#33ECFF"
    neon_blue_deep: str = "#00B4D6"
    neon_blue_dim:  str = "#062A33"
    neon_blue_glow: str = "#7FF2FF"

    # -- Tertiary accent (violet — Game Mode / Elite only) -------------------
    violet:         str = "#B070FF"
    violet_hot:     str = "#C99CFF"
    violet_deep:    str = "#8D4DFF"
    violet_dim:     str = "#1F1430"
    violet_glow:    str = "#D9B8FF"

    # -- Status colours ------------------------------------------------------
    amber:          str = "#FFB547"   # warning
    amber_dim:      str = "#3A2A12"
    coral:          str = "#FF6B4A"   # risk
    coral_dim:      str = "#3A1A12"
    red:            str = "#FF4757"   # critical
    red_dim:        str = "#3D1418"

    # -- Charting ------------------------------------------------------------
    chart_cpu:      str = "#A6FF00"   # lime
    chart_ram:      str = "#B070FF"   # violet
    chart_disk:     str = "#FFB547"   # amber
    chart_gpu:      str = "#00E4FF"   # cyan
    chart_net:      str = "#FF6BD0"   # magenta accent (chart only)
    chart_grid:     str = "#0E1620"

    # -- HUD-specific tokens (used by HexPanel / BracketCard / TickerBar) ----
    hex_line:       str = "#0F1923"   # base hex grid stroke
    hex_line_hot:   str = "#1B2A3A"   # hex grid highlight
    bracket:        str = "#A6FF00"   # corner brackets on panels
    bracket_dim:    str = "#3A5A05"
    glow_lime:      str = "#D4FF66"
    glow_cyan:      str = "#7FF2FF"

    # -- Signature gradients (ready for QSS ``qlineargradient(...)``) --------
    grad_brand:     str = (
        "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        "stop:0 #A6FF00, stop:1 #00E4FF)"
    )
    grad_cool:      str = (
        "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        "stop:0 #00E4FF, stop:1 #A6FF00)"
    )
    grad_royal:     str = (
        "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        "stop:0 #00E4FF, stop:1 #B070FF)"
    )
    grad_surface:   str = (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        "stop:0 #11171F, stop:1 #0A0E14)"
    )
    grad_sunken:    str = (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        "stop:0 #03050A, stop:1 #060A11)"
    )
    grad_lime_hot:  str = (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        "stop:0 #BFFF33, stop:1 #8DDE00)"
    )
    grad_cyan_hot:  str = (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        "stop:0 #33ECFF, stop:1 #00B4D6)"
    )

    # -- Semantic mapping for risk badges -----------------------------------
    def risk_color(self, risk: str) -> str:
        return {
            "safe":   self.accent,
            "low":    self.neon_blue,
            "medium": self.amber,
            "high":   self.coral,
        }.get(risk, self.text_secondary)

    def risk_dim(self, risk: str) -> str:
        return {
            "safe":   self.accent_dim,
            "low":    self.neon_blue_dim,
            "medium": self.amber_dim,
            "high":   self.coral_dim,
        }.get(risk, self.border)

    # -- Alpha helper (qlineargradient can't consume rgba alone, but QSS can)
    @staticmethod
    def with_alpha(hex_color: str, alpha: int) -> str:
        """Return CSS rgba() with alpha in 0..255 for the given #RRGGBB."""
        h = hex_color.lstrip("#")
        if len(h) != 6:
            return hex_color
        r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:], 16)
        return f"rgba({r},{g},{b},{alpha})"
