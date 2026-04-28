"""Settings view — configuration, mode selection, danger-zone actions."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core.app_controller import AppController
from ...core.constants import APP_NAME, APP_VERSION, MODE_ADVANCED, MODE_SAFE
from ...utils.paths import APP_DATA_DIR, LOG_DIR
from ..theme.palette import Palette
from ..theme.typography import Typography
from ..widgets.section import Card, DividerLine, SectionHeader
from ..widgets.toggle_switch import ToggleSwitch


class SettingsView(QWidget):
    def __init__(
        self,
        controller: AppController,
        palette: Palette,
        typography: Typography,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._ctrl = controller
        self._pal = palette
        self._type = typography

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        root = QVBoxLayout(container)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(18)

        root.addWidget(SectionHeader(
            "CONFIGURATION", "Settings",
            palette=palette, typography=typography,
        ))

        # -- Mode card
        mode_card = Card(palette=palette, padding=22)
        mode_card.body().addWidget(SectionHeader(
            "Optimization mode", "Choose your profile",
            palette=palette, typography=typography,
            eyebrow_color=palette.accent,
        ))

        group = QButtonGroup(self)
        self._safe_radio = QRadioButton("Safe  —  conservative suggestions only")
        self._adv_radio = QRadioButton("Advanced  —  include every reversible rule")
        for rb in (self._safe_radio, self._adv_radio):
            rb.setFont(typography.body())
            rb.setCursor(Qt.CursorShape.PointingHandCursor)
            group.addButton(rb)
            mode_card.body().addWidget(rb)

        self._safe_radio.setChecked(controller.config.mode == MODE_SAFE)
        self._adv_radio.setChecked(controller.config.mode == MODE_ADVANCED)
        self._safe_radio.toggled.connect(lambda on: on and self._set_mode(MODE_SAFE))
        self._adv_radio.toggled.connect(lambda on: on and self._set_mode(MODE_ADVANCED))

        root.addWidget(mode_card)

        # -- Toggles card
        toggles_card = Card(palette=palette, padding=22)
        toggles_card.body().addWidget(SectionHeader(
            "Behavior", "Default behavior",
            palette=palette, typography=typography,
            eyebrow_color=palette.violet,
        ))

        self._rp_toggle = self._toggle_row(
            "Create restore point before applying a plan",
            "Windows System Restore point, requires admin. Skipped gracefully without admin.",
            controller.config.create_restore_point,
        )
        toggles_card.body().addLayout(self._rp_toggle["row"])

        self._backup_toggle = self._toggle_row(
            "Auto-backup each setting we change",
            "Required for per-action rollback from the Safety tab.",
            controller.config.auto_backup,
        )
        toggles_card.body().addLayout(self._backup_toggle["row"])

        self._confirm_toggle = self._toggle_row(
            "Always confirm cleanup before deleting",
            "Shows the full file list in a dialog. Recommended on.",
            controller.config.confirm_cleanup,
        )
        toggles_card.body().addLayout(self._confirm_toggle["row"])

        self._anim_toggle = self._toggle_row(
            "Enable UI animations",
            "Small motion on toggles, gauges, and sidebar. Disable on very old machines.",
            controller.config.enable_animations,
        )
        toggles_card.body().addLayout(self._anim_toggle["row"])

        self._tray_toggle = self._toggle_row(
            "Minimize to tray instead of exit",
            "Clicking [X] hides the window — the tray icon keeps Game Mode auto-detect and the HUD alive.",
            controller.config.minimize_to_tray,
        )
        toggles_card.body().addLayout(self._tray_toggle["row"])

        self._auto_gm_toggle = self._toggle_row(
            "Auto-activate Game Mode on fullscreen game",
            "Detects any fullscreen app using >40 MB RAM; reverts automatically when it closes.",
            controller.config.auto_game_mode,
        )
        toggles_card.body().addLayout(self._auto_gm_toggle["row"])

        self._auto_hud_toggle = self._toggle_row(
            "Auto-show HUD overlay during games",
            "Pairs with auto Game Mode. HUD hides itself when the game ends.",
            controller.config.auto_hud_on_game,
        )
        toggles_card.body().addLayout(self._auto_hud_toggle["row"])

        root.addWidget(toggles_card)

        # -- AutoPilot
        autopilot_card = Card(palette=palette, padding=22)
        autopilot_card.body().addWidget(SectionHeader(
            "AutoPilot", "Hands-free automation",
            palette=palette, typography=typography,
            eyebrow_color=palette.accent,
        ))
        autopilot_blurb = QLabel(
            "When AutoPilot is on, GameBoost silently applies the safe Recommended "
            "preset, swaps to per-game profiles when a game starts, and resolves "
            "critical insights automatically. Everything stays reversible from "
            "the Safety tab."
        )
        autopilot_blurb.setWordWrap(True)
        autopilot_blurb.setFont(typography.body())
        autopilot_blurb.setStyleSheet(f"color: {palette.text_secondary};")
        autopilot_card.body().addWidget(autopilot_blurb)

        self._autopilot_master_toggle = self._toggle_row(
            "AutoPilot — silent automation master switch",
            "Off by default. Turn this on for true 'set-and-forget' behaviour.",
            controller.config.autopilot_enabled,
        )
        autopilot_card.body().addLayout(self._autopilot_master_toggle["row"])

        self._autopilot_recommend_toggle = self._toggle_row(
            "Apply Recommended preset on boot",
            "Once per day, applies only safe rules from the Recommended plan.",
            controller.config.autopilot_apply_recommended,
        )
        autopilot_card.body().addLayout(self._autopilot_recommend_toggle["row"])

        self._autopilot_per_game_toggle = self._toggle_row(
            "Activate per-game profile when a game starts",
            "Switches power plan, sets process priority, suspends background apps "
            "you've added, then restores baseline on exit.",
            controller.config.autopilot_per_game_profiles,
        )
        autopilot_card.body().addLayout(self._autopilot_per_game_toggle["row"])

        self._autopilot_insights_toggle = self._toggle_row(
            "Resolve critical insights automatically",
            "Limited to a curated, audited list of safe automatic fixes.",
            controller.config.autopilot_act_on_insights,
        )
        autopilot_card.body().addLayout(self._autopilot_insights_toggle["row"])

        root.addWidget(autopilot_card)

        # -- Privacy & ads
        privacy_card = Card(palette=palette, padding=22)
        privacy_card.body().addWidget(SectionHeader(
            "Privacy & ads", "What's collected, what's shown",
            palette=palette, typography=typography,
            eyebrow_color=palette.neon_blue,
        ))

        privacy_blurb = QLabel(
            "GameBoost runs entirely on your PC. Banners are sponsored "
            "and clicking them opens your default browser. See PRIVACY.md "
            "in the app folder for the full policy."
        )
        privacy_blurb.setWordWrap(True)
        privacy_blurb.setFont(typography.body())
        privacy_blurb.setStyleSheet(f"color: {palette.text_secondary};")
        privacy_card.body().addWidget(privacy_blurb)

        self._sponsored_cards_toggle = self._toggle_row(
            "Sponsored insight cards",
            "Show curated, clearly-labelled 'Sponsored' partner cards "
            "inside Live Insights alongside system suggestions.",
            controller.config.sponsored_cards_enabled,
        )
        privacy_card.body().addLayout(self._sponsored_cards_toggle["row"])

        self._personalized_ads_toggle = self._toggle_row(
            "Allow personalized ads",
            "Off by default. When off, you'll see non-personalized ads only "
            "(GDPR / CCPA / UK GDPR — your right to refuse profiling).",
            controller.config.personalized_ads,
        )
        privacy_card.body().addLayout(self._personalized_ads_toggle["row"])

        root.addWidget(privacy_card)

        # -- Paths / diagnostic
        info_card = Card(palette=palette, padding=22)
        info_card.body().addWidget(SectionHeader(
            "Diagnostics", "Paths & logs",
            palette=palette, typography=typography,
            eyebrow_color=palette.amber,
        ))

        info_card.body().addWidget(_InfoRow("App data", str(APP_DATA_DIR), palette, typography))
        info_card.body().addWidget(_InfoRow("Log file", str(LOG_DIR / "gameboost.log"), palette, typography))

        log_btns = QHBoxLayout()
        log_btns.setSpacing(8)
        open_log = QPushButton("Copy log path")
        open_log.setProperty("variant", "ghost")
        open_log.setCursor(Qt.CursorShape.PointingHandCursor)
        open_log.clicked.connect(self._copy_log_path)
        log_btns.addWidget(open_log)

        export_log = QPushButton("Export log to…")
        export_log.setProperty("variant", "ghost")
        export_log.setCursor(Qt.CursorShape.PointingHandCursor)
        export_log.clicked.connect(self._export_log)
        log_btns.addWidget(export_log)

        export_diag = QPushButton("Export diagnostics bundle (zip)…")
        export_diag.setProperty("variant", "ghost")
        export_diag.setCursor(Qt.CursorShape.PointingHandCursor)
        export_diag.setToolTip(
            "Zip containing the log tail, action history, hardware snapshot, "
            "current plan, and Windows/Python/PyQt versions. Nothing else."
        )
        export_diag.clicked.connect(self._export_diagnostics)
        log_btns.addWidget(export_diag)

        log_btns.addStretch()
        info_card.body().addLayout(log_btns)

        root.addWidget(info_card)

        # -- About
        about_card = Card(palette=palette, padding=22)
        about_card.body().addWidget(SectionHeader(
            "About", f"{APP_NAME}",
            palette=palette, typography=typography,
            eyebrow_color=palette.text_secondary,
        ))
        tagline = QLabel(
            f"Version {APP_VERSION}. Fully offline. No telemetry, no accounts, "
            "no paid APIs. Source-available and auditable."
        )
        tagline.setWordWrap(True)
        tagline.setFont(typography.body())
        tagline.setStyleSheet(f"color: {palette.text_secondary};")
        about_card.body().addWidget(tagline)
        root.addWidget(about_card)

        root.addStretch()

    # ------------------------------------------------------------------ helpers
    def _toggle_row(self, title: str, subtitle: str, initial: bool) -> dict:
        row = QHBoxLayout()
        row.setContentsMargins(0, 8, 0, 8)
        row.setSpacing(18)

        texts = QVBoxLayout()
        texts.setSpacing(2)
        t = QLabel(title)
        t.setFont(self._type.body_strong())
        t.setCursor(Qt.CursorShape.PointingHandCursor)
        s = QLabel(subtitle)
        s.setWordWrap(True)
        s.setFont(self._type.small())
        s.setStyleSheet(f"color: {self._pal.text_secondary};")
        s.setCursor(Qt.CursorShape.PointingHandCursor)
        texts.addWidget(t)
        texts.addWidget(s)
        row.addLayout(texts, 1)

        toggle = ToggleSwitch(self._pal)
        toggle.setChecked(initial)
        toggle.toggled.connect(lambda val, key=title: self._on_toggle(title, val))
        row.addWidget(toggle, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        # Clicking the title or subtitle text flips the toggle, matching the
        # affordance suggested by the pointer cursor.
        def _click_proxy(_event, _t=toggle):
            _t.setChecked(not _t.isChecked())
        t.mousePressEvent = _click_proxy   # type: ignore[assignment]
        s.mousePressEvent = _click_proxy   # type: ignore[assignment]

        return {"row": row, "toggle": toggle}

    def _on_toggle(self, title: str, value: bool) -> None:
        mapping = {
            "Create restore point before applying a plan": "create_restore_point",
            "Auto-backup each setting we change": "auto_backup",
            "Always confirm cleanup before deleting": "confirm_cleanup",
            "Enable UI animations": "enable_animations",
            "Minimize to tray instead of exit": "minimize_to_tray",
            "Auto-activate Game Mode on fullscreen game": "auto_game_mode",
            "Auto-show HUD overlay during games": "auto_hud_on_game",
            "Apply Recommended preset on boot":
                "autopilot_apply_recommended",
            "Activate per-game profile when a game starts":
                "autopilot_per_game_profiles",
            "Resolve critical insights automatically":
                "autopilot_act_on_insights",
            "Sponsored insight cards": "sponsored_cards_enabled",
            "Allow personalized ads": "personalized_ads",
        }
        # Master AutoPilot switch goes through the controller so the boot
        # pass fires immediately on enable.
        if title.startswith("AutoPilot"):
            ap = getattr(self._ctrl, "autopilot", None)
            if ap is not None:
                ap.set_enabled(value)
            else:
                self._ctrl.config.update(autopilot_enabled=value)
            return
        key = mapping.get(title)
        if key:
            self._ctrl.config.update(**{key: value})

    def _set_mode(self, mode: str) -> None:
        self._ctrl.config.update(mode=mode)

    def _copy_log_path(self) -> None:
        from PyQt6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setText(str(LOG_DIR / "gameboost.log"))
        QMessageBox.information(self, "Copied", "Log path copied to clipboard.")

    def _export_log(self) -> None:
        from pathlib import Path

        default = str(Path.home() / "Downloads" / "gameboost.log")
        path, _ = QFileDialog.getSaveFileName(self, "Export log", default, "Log files (*.log)")
        if not path:
            return
        src = LOG_DIR / "gameboost.log"
        if not src.exists():
            QMessageBox.warning(self, "Export log", "No log file yet.")
            return
        Path(path).write_bytes(src.read_bytes())
        QMessageBox.information(self, "Export complete", f"Log copied to {path}.")

    def _export_diagnostics(self) -> None:
        from pathlib import Path
        from ...utils.diagnostics import export_bundle

        default = str(Path.home() / "Downloads" / "gameboost-diagnostics.zip")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export diagnostics bundle", default, "Zip archives (*.zip)"
        )
        if not path:
            return
        try:
            plan = None
            try:
                plan = self._ctrl.optimizer.generate_plan(
                    self._ctrl.hardware_snapshot or self._ctrl.hardware.detect()
                )
            except Exception:
                pass
            final = export_bundle(
                Path(path),
                hardware=self._ctrl.hardware_snapshot,
                plan=plan,
            )
            QMessageBox.information(
                self,
                "Diagnostics exported",
                f"Bundle saved to:\n{final}\n\n"
                "Safe to share — contains no personal data outside the app's own folder.",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Export diagnostics",
                                f"Couldn't export bundle: {exc}")


class _InfoRow(QFrame):
    def __init__(self, key: str, value: str, palette: Palette, typography: Typography, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("role", "card-inset")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)
        k = QLabel(key)
        k.setFont(typography.small())
        k.setStyleSheet(f"color: {palette.text_tertiary};")
        k.setFixedWidth(90)
        v = QLabel(value)
        v.setFont(typography.small())
        v.setStyleSheet(f"color: {palette.text_primary};")
        v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.setWordWrap(True)
        lay.addWidget(k)
        lay.addWidget(v, 1)
