"""Game Hub view — the gaming-focused launcher + per-game tuning grid.

Top-level structure:

    [ Eyebrow ]  GAME LIBRARY                              [ RESCAN ]
    [ Search _____ ]  [ All ▼ ]  [ Recent ▼ ]                 12 GAMES

    +---------- HudFrame: Library grid ----------+
    | [tile] [tile] [tile] [tile] [tile] ...     |
    | [tile] [tile] [tile] [tile] [tile] ...     |
    +---------------------------------------------+

Tile clicks open a modal-ish profile editor inline. The Hub talks
exclusively to :class:`GameHubViewModel` — no direct controller access.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...games.library import Launcher
from ..theme.palette import Palette
from ..theme.typography import Typography
from ..viewmodels.game_hub_vm import GameHubViewModel
from ..widgets.game_tile import GameTile
from ...monetization import AdBanner


class GameHubView(QWidget):
    def __init__(
        self,
        vm: GameHubViewModel,
        palette: Palette,
        typography: Typography,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._vm = vm
        self._pal = palette
        self._type = typography
        self._tiles: list[GameTile] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(body)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)

        # ----- Header --------------------------------------------------------
        header = QHBoxLayout()
        header.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        eyebrow = QLabel("GAME LIBRARY")
        eyebrow.setFont(typography.eyebrow())
        eyebrow.setStyleSheet(f"color: {palette.accent};")
        title_col.addWidget(eyebrow)

        title = QLabel("Your Hub")
        title.setFont(typography.display_h1())
        title.setStyleSheet(f"color: {palette.text_primary};")
        title_col.addWidget(title)
        header.addLayout(title_col)
        header.addStretch()

        self._count_label = QLabel("0 GAMES")
        self._count_label.setFont(typography.eyebrow())
        self._count_label.setStyleSheet(f"color: {palette.text_tertiary};")
        header.addWidget(self._count_label)

        self._rescan_btn = QPushButton("RESCAN")
        self._rescan_btn.setProperty("variant", "ghost")
        self._rescan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rescan_btn.clicked.connect(self._on_rescan)
        header.addWidget(self._rescan_btn)
        root.addLayout(header)

        # ----- Filter row ----------------------------------------------------
        filters = QHBoxLayout()
        filters.setSpacing(10)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search your library…")
        self._search.textChanged.connect(self._refilter)
        filters.addWidget(self._search, 2)

        self._launcher_combo = QComboBox()
        self._launcher_combo.addItem("All launchers", userData="all")
        for ln in Launcher:
            self._launcher_combo.addItem(ln.label, userData=ln.value)
        self._launcher_combo.currentIndexChanged.connect(self._refilter)
        filters.addWidget(self._launcher_combo, 1)

        self._sort_combo = QComboBox()
        self._sort_combo.addItem("Recently played", userData="recent")
        self._sort_combo.addItem("A → Z",            userData="alpha")
        self._sort_combo.addItem("Launcher",         userData="launcher")
        self._sort_combo.currentIndexChanged.connect(self._refilter)
        filters.addWidget(self._sort_combo, 1)

        root.addLayout(filters)

        # ----- Empty / status note ------------------------------------------
        self._status_note = QLabel("Loading library…")
        self._status_note.setFont(typography.body())
        self._status_note.setStyleSheet(f"color: {palette.text_secondary};")
        root.addWidget(self._status_note)

        # ----- Grid ----------------------------------------------------------
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(14)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        root.addWidget(self._grid_host)

        # -- Sponsored banner (self-hides if ads_enabled=False)
        self.ad_banner = AdBanner(
            vm.controller.config, palette, typography, slot="game_hub",
        )
        root.addWidget(self.ad_banner)

        root.addStretch(1)

        # ----- VM bindings ---------------------------------------------------
        vm.library_changed.connect(self._on_library_changed)
        vm.scanning_changed.connect(self._on_scanning_changed)

        # First paint with whatever the cache holds
        QTimer.singleShot(0, lambda: self._on_library_changed(vm.games))
        # Trigger a scan in the background after the UI shows
        QTimer.singleShot(800, vm.rescan)

    # ------------------------------------------------------------------ slots
    def _on_rescan(self) -> None:
        self._vm.rescan()

    def _on_scanning_changed(self, scanning: bool) -> None:
        if scanning:
            self._rescan_btn.setText("SCANNING…")
            self._rescan_btn.setEnabled(False)
            self._status_note.setText("Scanning installed launchers — this only takes a moment.")
            self._status_note.setVisible(True)
        else:
            self._rescan_btn.setText("RESCAN")
            self._rescan_btn.setEnabled(True)

    def _on_library_changed(self, games) -> None:
        self._render(games)

    def _refilter(self) -> None:
        self._render(self._vm.games)

    # ------------------------------------------------------------------ render
    def _render(self, games) -> None:
        # Filter
        query = self._search.text().strip().lower()
        ln_filter = self._launcher_combo.currentData()
        sort_key = self._sort_combo.currentData()

        filtered = [g for g in games if (not query or query in g.name.lower())]
        if ln_filter and ln_filter != "all":
            filtered = [g for g in filtered if g.launcher.value == ln_filter]
        if sort_key == "alpha":
            filtered.sort(key=lambda g: g.name.lower())
        elif sort_key == "launcher":
            filtered.sort(key=lambda g: (g.launcher.label, g.name.lower()))
        else:
            filtered.sort(key=lambda g: (-g.last_played, g.name.lower()))

        self._count_label.setText(f"{len(filtered)} GAMES")

        # Clear current tiles
        for t in self._tiles:
            t.setParent(None)
            t.deleteLater()
        self._tiles.clear()

        if not filtered:
            self._status_note.setText(
                "No games detected. Press RESCAN to look again, or install a "
                "supported launcher (Steam, Epic, GOG, Battle.net, Riot, Xbox)."
            )
            self._status_note.setVisible(True)
            return
        self._status_note.setVisible(False)

        # Lay tiles in a fixed-column grid; the grid auto-rows on overflow.
        cols = max(2, min(6, max(1, self.width() // 240)))
        for idx, g in enumerate(filtered):
            tile = GameTile(g, self._pal, self._type, self)
            tile.play_clicked.connect(self._on_play)
            tile.tune_clicked.connect(self._on_tune)
            tile.activated.connect(self._on_tune)
            r, c = divmod(idx, cols)
            self._grid.addWidget(tile, r, c)
            self._tiles.append(tile)

    # ------------------------------------------------------------------ actions
    def _on_play(self, game_id: str) -> None:
        ok = self._vm.launch(game_id)
        if not ok:
            QMessageBox.warning(
                self, "Couldn't launch",
                "The game's executable or launcher URI couldn't be resolved.",
            )

    def _on_tune(self, game_id: str) -> None:
        applied = self._vm.apply_profile_now(game_id)
        if applied:
            QMessageBox.information(
                self, "Profile applied",
                "Per-game profile is now active. It will roll back automatically "
                "when the game closes (or when you press Restore from this dialog).",
            )
        else:
            QMessageBox.warning(
                self, "Profile error",
                "Couldn't apply the profile. Check Logs from Settings.",
            )

    # Keep the column count responsive
    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        self._render(self._vm.games)
