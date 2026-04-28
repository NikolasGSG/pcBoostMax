"""Apex global QSS generator.

Produces one big stylesheet string that, when applied to the QApplication,
overrides Qt's default chrome head-to-toe in the GameBoost "Apex" style:
obsidian black, hairline rules, flat lime/cyan accents, tight radii.
"""
from __future__ import annotations

from .palette import Palette
from .spacing import Radius, Spacing


def build_stylesheet(p: Palette, r: Radius, s: Spacing) -> str:
    return f"""
/* ============================================================
   GLOBAL
   ============================================================ */
* {{
    outline: 0;
}}

QWidget {{
    color: {p.text_primary};
    background: transparent;
    selection-background-color: {p.accent};
    selection-color: {p.text_on_accent};
}}

QMainWindow, #RootSurface {{
    background-color: {p.bg_base};
}}

/* Obsidian shell with a vignette-like cool tint at the centre. */
#RootSurface {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p.bg_base},
        stop:0.5 #08101A,
        stop:1 {p.bg_base});
}}

QToolTip {{
    background-color: {p.bg_elevated};
    color: {p.text_primary};
    border: 1px solid {p.accent};
    border-radius: 2px;
    padding: 6px 10px;
    font-weight: 600;
}}

/* ============================================================
   SCROLLBARS — hairline rail with lime-cyan track on hover
   ============================================================ */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 6px 2px 6px 0;
}}
QScrollBar::handle:vertical {{
    background: {p.border_strong};
    border-radius: 1px;
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p.accent};
}}
QScrollBar::handle:vertical:pressed {{
    background: {p.accent_pressed};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent; border: none; height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0 6px 2px 6px;
}}
QScrollBar::handle:horizontal {{
    background: {p.border_strong};
    border-radius: 1px;
    min-width: 40px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {p.accent};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent; border: none; width: 0;
}}

/* ============================================================
   PRIMITIVE CARD — flat surfaces, hairline borders, sharp corners
   ============================================================ */
QFrame[role="card"] {{
    background-color: {p.bg_surface};
    border: 1px solid {p.border_hairline};
    border-radius: 4px;
}}
QFrame[role="card"]:hover {{
    border-color: {p.border_strong};
}}
QFrame[role="card-elevated"] {{
    background-color: {p.bg_elevated};
    border: 1px solid {p.border};
    border-radius: 4px;
}}
QFrame[role="card-hero"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0.4,
        stop:0 {p.bg_surface}, stop:1 {p.bg_elevated});
    border: 1px solid {p.border_strong};
    border-radius: 4px;
}}
QFrame[role="card-glass"] {{
    background-color: rgba(14,20,28,0.92);
    border: 1px solid {p.border_hairline};
    border-radius: 4px;
}}
QFrame[role="card-inset"] {{
    background-color: {p.bg_sunken};
    border: 1px solid {p.border_soft};
    border-radius: 3px;
}}
QFrame[role="divider"] {{
    background-color: {p.border_hairline};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}
/* Apex hex-bracket card — corners painted via BracketCard widget */
QFrame[role="hex-card"] {{
    background-color: {p.bg_surface};
    border: 1px solid {p.border_hairline};
    border-radius: 0px;
}}
/* Insight cards keep a coloured stripe on the left only */
QFrame[role="insight-card"] {{
    border-radius: 3px;
}}

/* ============================================================
   TEXT ROLES
   ============================================================ */
QLabel[role="display"]   {{ color: {p.text_primary}; letter-spacing: 0; }}
QLabel[role="h1"]        {{ color: {p.text_primary}; letter-spacing: 0; }}
QLabel[role="h2"]        {{ color: {p.text_primary}; }}
QLabel[role="body"]      {{ color: {p.text_primary}; }}
QLabel[role="muted"]     {{ color: {p.text_secondary}; }}
QLabel[role="dim"]       {{ color: {p.text_tertiary}; }}
QLabel[role="eyebrow"]        {{ color: {p.accent}; }}
QLabel[role="eyebrow-cyan"]   {{ color: {p.neon_blue}; }}
QLabel[role="eyebrow-violet"] {{ color: {p.violet}; }}
/* HUD numerics — mono, lime by default */
QLabel[role="hud"]     {{ color: {p.accent}; }}
QLabel[role="hud-cyan"]   {{ color: {p.neon_blue}; }}
QLabel[role="hud-violet"] {{ color: {p.violet}; }}
QLabel[role="hud-amber"]  {{ color: {p.amber}; }}
QLabel[role="hud-coral"]  {{ color: {p.coral}; }}

/* ============================================================
   BUTTONS — Apex hardware-style: flat dark with hairline
   accents, primary = solid lime fill
   ============================================================ */
QPushButton {{
    background-color: {p.bg_elevated};
    color: {p.text_primary};
    border: 1px solid {p.border_hairline};
    border-radius: 2px;
    padding: 9px 18px;
    font-weight: 600;
    letter-spacing: 0.4px;
}}
QPushButton:hover {{
    background-color: #1A2230;
    border-color: {p.neon_blue};
    color: {p.neon_blue_hot};
}}
QPushButton:pressed {{ background-color: {p.bg_surface}; }}
QPushButton:disabled {{
    color: {p.text_disabled};
    background-color: {p.bg_surface};
    border-color: {p.border_soft};
}}

/* PRIMARY: solid lime fill, dark text — the "main action" anchor */
QPushButton[variant="primary"] {{
    background-color: {p.accent};
    color: {p.text_on_accent};
    border: 1px solid {p.accent};
    padding: 11px 24px;
    font-weight: 800;
    letter-spacing: 1.0px;
}}
QPushButton[variant="primary"]:hover {{
    background-color: {p.accent_hover};
    border-color: {p.accent_glow};
}}
QPushButton[variant="primary"]:pressed {{ background-color: {p.accent_pressed}; }}
QPushButton[variant="primary"]:disabled {{
    background-color: {p.accent_dim};
    color: {p.text_tertiary};
    border-color: {p.accent_dim};
}}

/* GHOST: hairline outlined, fills toward lime on hover */
QPushButton[variant="ghost"] {{
    background-color: transparent;
    border: 1px solid {p.border_hairline};
    color: {p.text_secondary};
    font-weight: 700;
    letter-spacing: 0.6px;
}}
QPushButton[variant="ghost"]:hover {{
    background-color: {p.accent_dim};
    border-color: {p.accent};
    color: {p.accent};
}}
QPushButton[variant="ghost"]:pressed {{ background-color: transparent; }}

/* DANGER: coral hairline, fills on hover */
QPushButton[variant="danger"] {{
    background-color: transparent;
    border: 1px solid {p.coral};
    color: {p.coral};
    font-weight: 700;
}}
QPushButton[variant="danger"]:hover {{
    background-color: {p.coral_dim};
    border-color: {p.red};
    color: {p.red};
}}

/* VIOLET: Elite tier (Game Mode, Absolute) */
QPushButton[variant="violet"] {{
    background-color: {p.violet};
    color: #0E0420;
    border: 1px solid {p.violet_glow};
    font-weight: 800;
    letter-spacing: 0.8px;
    padding: 11px 24px;
}}
QPushButton[variant="violet"]:hover {{
    background-color: {p.violet_hot};
    border-color: {p.violet_glow};
}}
QPushButton[variant="violet"]:pressed {{ background-color: {p.violet_deep}; }}

/* COOL: cyan secondary — telemetry / monitor actions */
QPushButton[variant="cool"] {{
    background-color: {p.neon_blue};
    color: #04161B;
    border: 1px solid {p.neon_blue};
    font-weight: 800;
    letter-spacing: 0.8px;
    padding: 11px 24px;
}}
QPushButton[variant="cool"]:hover {{
    background-color: {p.neon_blue_hot};
    border-color: {p.neon_blue_glow};
}}

/* ROYAL: cyan → violet gradient (rare — tier-up CTAs) */
QPushButton[variant="royal"] {{
    background: {p.grad_royal};
    color: #0B0B1C;
    border: 1px solid {p.violet_glow};
    font-weight: 800;
    letter-spacing: 0.8px;
    padding: 11px 24px;
}}
QPushButton[variant="royal"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {p.neon_blue_hot}, stop:1 {p.violet_hot});
}}

/* BRAND: lime → cyan — the "go beast mode" Absolute CTA */
QPushButton[variant="brand"] {{
    background: {p.grad_brand};
    color: #04140A;
    border: 1px solid {p.accent_glow};
    font-weight: 900;
    letter-spacing: 1.6px;
    padding: 12px 28px;
}}
QPushButton[variant="brand"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {p.accent_hover}, stop:1 {p.neon_blue_hot});
    border-color: {p.glow_lime};
}}

/* Hotkey "modifier" chip button — small, toggleable */
QPushButton[variant="mod"] {{
    background-color: {p.bg_sunken};
    border: 1px solid {p.border};
    color: {p.text_secondary};
    padding: 6px 14px;
    font-weight: 700;
    letter-spacing: 1.4px;
    border-radius: 2px;
}}
QPushButton[variant="mod"]:hover {{
    background-color: {p.bg_elevated};
    border-color: {p.border_strong};
    color: {p.text_primary};
}}
QPushButton[variant="mod"]:checked {{
    background-color: {p.accent_dim};
    border-color: {p.accent};
    color: {p.accent};
}}

/* Tile button (game library) — huge tap target with image background */
QPushButton[variant="tile"] {{
    background-color: {p.bg_surface};
    border: 1px solid {p.border_hairline};
    border-radius: 4px;
    padding: 0;
    text-align: left;
}}
QPushButton[variant="tile"]:hover {{
    border-color: {p.accent};
}}

/* ============================================================
   LINE / COMBO / SPIN — hairline inputs with cyan focus ring
   ============================================================ */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {p.bg_sunken};
    border: 1px solid {p.border_hairline};
    border-radius: 2px;
    padding: 9px 12px;
    color: {p.text_primary};
    selection-background-color: {p.accent};
    selection-color: {p.text_on_accent};
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {p.border_strong};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: {p.neon_blue};
    background-color: {p.bg_base};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
QComboBox QAbstractItemView {{
    background-color: {p.bg_elevated};
    border: 1px solid {p.border_strong};
    border-radius: 2px;
    selection-background-color: {p.accent_dim};
    selection-color: {p.accent};
    padding: 4px;
}}

/* ============================================================
   PROGRESS BARS — slim hairline rail with lime fill
   ============================================================ */
QProgressBar {{
    background-color: {p.bg_sunken};
    border: 1px solid {p.border_soft};
    border-radius: 1px;
    min-height: 6px;
    max-height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {p.accent};
    border-radius: 0;
}}
QProgressBar[variant="cyan"]::chunk   {{ background: {p.neon_blue}; }}
QProgressBar[variant="violet"]::chunk {{ background: {p.violet}; }}
QProgressBar[variant="amber"]::chunk  {{ background: {p.amber}; }}
QProgressBar[variant="coral"]::chunk  {{ background: {p.coral}; }}

/* ============================================================
   GROUP / TAB
   ============================================================ */
QGroupBox {{
    background-color: {p.bg_surface};
    border: 1px solid {p.border_soft};
    border-radius: {r.lg}px;
    margin-top: 18px;
    padding: 16px;
    color: {p.text_primary};
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    color: {p.text_secondary};
}}

QTabBar::tab {{
    background: transparent;
    color: {p.text_secondary};
    padding: 8px 18px;
    border: none;
    border-bottom: 2px solid transparent;
    font-weight: 700;
    letter-spacing: 1.0px;
}}
QTabBar::tab:hover {{ color: {p.neon_blue}; }}
QTabBar::tab:selected {{
    color: {p.accent};
    border-bottom: 2px solid {p.accent};
}}
QTabWidget::pane {{ border: none; }}

/* ============================================================
   CHECKBOX (used only for simple toggles outside our ToggleSwitch)
   ============================================================ */
QCheckBox {{ color: {p.text_primary}; spacing: 10px; }}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border-radius: 4px;
    border: 1px solid {p.border_strong};
    background: {p.bg_sunken};
}}
QCheckBox::indicator:hover {{ border-color: {p.accent}; }}
QCheckBox::indicator:checked {{
    background: {p.accent};
    border-color: {p.accent};
    image: none;
}}

/* ============================================================
   RADIO BUTTON — visible on dark background with lime fill
   ============================================================ */
QRadioButton {{
    color: {p.text_primary};
    spacing: 10px;
    padding: 4px 0;
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 9px;
    border: 1px solid {p.border_strong};
    background: {p.bg_sunken};
}}
QRadioButton::indicator:hover {{
    border-color: {p.accent};
    background: {p.bg_elevated};
}}
QRadioButton::indicator:checked {{
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
        stop:0 {p.accent}, stop:0.45 {p.accent},
        stop:0.5 {p.bg_sunken}, stop:1 {p.bg_sunken});
    border: 1px solid {p.accent};
}}
QRadioButton:disabled {{ color: {p.text_disabled}; }}
QRadioButton::indicator:disabled {{
    border-color: {p.border_soft};
    background: {p.bg_surface};
}}

/* ============================================================
   STATUS BANNER (role-tinted) — thin left bar accent style
   ============================================================ */
QFrame[role="banner-info"]    {{ background: rgba(166,255,0,0.06);  border: 1px solid {p.accent};    border-left: 3px solid {p.accent};    border-radius: 2px; }}
QFrame[role="banner-warn"]    {{ background: rgba(255,181,71,0.06); border: 1px solid {p.amber};     border-left: 3px solid {p.amber};     border-radius: 2px; }}
QFrame[role="banner-danger"]  {{ background: rgba(255,71,87,0.06);  border: 1px solid {p.red};       border-left: 3px solid {p.red};       border-radius: 2px; }}
QFrame[role="banner-violet"]  {{ background: rgba(176,112,255,0.06);border: 1px solid {p.violet};    border-left: 3px solid {p.violet};    border-radius: 2px; }}
QFrame[role="banner-cyan"]    {{ background: rgba(0,228,255,0.06);  border: 1px solid {p.neon_blue}; border-left: 3px solid {p.neon_blue}; border-radius: 2px; }}

/* ============================================================
   TABLES (cleanup preview, action history)
   ============================================================ */
QTableView, QTreeView, QListView {{
    background-color: {p.bg_sunken};
    border: 1px solid {p.border_soft};
    border-radius: {r.md}px;
    gridline-color: {p.border_soft};
    selection-background-color: {p.accent_dim};
    selection-color: {p.text_primary};
    alternate-background-color: {p.bg_surface};
}}
QHeaderView::section {{
    background-color: {p.bg_surface};
    color: {p.text_secondary};
    border: none;
    border-bottom: 1px solid {p.border};
    padding: 8px 12px;
    font-weight: 600;
}}
QTableView::item, QTreeView::item, QListView::item {{ padding: 6px 8px; }}

/* ============================================================
   SIDEBAR — obsidian rail with lime active-track
   ============================================================ */
#Sidebar {{
    background-color: {p.bg_sunken};
    border-right: 1px solid {p.border_hairline};
}}
#SidebarBrand {{ color: {p.accent}; letter-spacing: 3px; }}

#NavItem {{
    background-color: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0px;
    text-align: left;
    padding: 11px 14px 11px 18px;
    color: {p.text_secondary};
    font-weight: 700;
    letter-spacing: 1.0px;
}}
#NavItem:hover {{
    background-color: {p.bg_surface};
    color: {p.text_primary};
    border-left-color: {p.border_strong};
}}
#NavItem[active="true"] {{
    background-color: {p.accent_dim};
    color: {p.accent};
    border-left: 3px solid {p.accent};
}}

/* ============================================================
   TICKER BAR (top-of-window live HUD readout)
   ============================================================ */
#TickerBar {{
    background-color: {p.bg_sunken};
    border-bottom: 1px solid {p.border_hairline};
}}
#TickerCell {{
    background-color: transparent;
    border-right: 1px solid {p.border_soft};
}}
#TopBar {{
    background-color: {p.bg_base};
    border-bottom: 1px solid {p.border_hairline};
}}

/* ============================================================
   GAME TILE (used by Game Hub)
   ============================================================ */
#GameTile {{
    background-color: {p.bg_surface};
    border: 1px solid {p.border_hairline};
    border-radius: 4px;
}}
#GameTile:hover {{
    border-color: {p.accent};
}}
#GameTileTitle {{
    color: {p.text_primary};
    font-weight: 700;
}}
#GameTileSub {{
    color: {p.text_secondary};
}}
"""
