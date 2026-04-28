"""Native Qt banner widget — ToS-compliant ad surface.

We deliberately do NOT embed a WebView here. Reasons:

1. AdSense ToS §3.6 forbids ad serving inside non-browser desktop apps.
2. Microsoft Advertising no longer ships an SDK for desktop apps.
3. QtWebEngine adds ~100 MB to the binary.

Instead, this widget:

* Loads a JSON manifest of house / sponsored creatives via
  :mod:`app.monetization.house_ads`.
* Renders the chosen creative as a native Qt card (image + headline +
  body + CTA + small "Sponsored" disclosure).
* On click, opens the user's default browser at a UTM-tagged URL.
  That destination page (which we host) can run AdSense + Microsoft
  Advertising tags **legitimately** — the desktop app is just a
  traffic source.

This pattern is exactly what consumer optimizers like CCleaner and
IObit use to monetize without violating any ad-network ToS.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from ..core.config import AppConfig
from ..ui.theme.palette import Palette
from ..ui.theme.typography import Typography
from ..utils.logger import get_logger
from . import house_ads as house

log = get_logger("monetization.ad_banner")

DEFAULT_HEIGHT = 96
SLOT_NAME = "banner"


# ---------------------------------------------------------------- worker
class _ManifestWorker(QObject):
    ready = pyqtSignal(object)   # Manifest
    finished = pyqtSignal()

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url

    def run(self) -> None:
        try:
            manifest = house.fetch(self._url)
            self.ready.emit(manifest)
        except Exception:
            log.exception("manifest worker crashed")
        finally:
            self.finished.emit()


# ---------------------------------------------------------------- widget
class AdBanner(QFrame):
    """Native Qt banner widget. Self-hides when ads are disabled.

    Click handler opens the system browser at the creative's UTM-tagged
    click URL — never inside the app.
    """

    def __init__(
        self,
        config: AppConfig,
        palette: Palette,
        typography: Typography,
        *,
        slot: str = SLOT_NAME,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._pal = palette
        self._type = typography
        self._slot = slot
        self._creative: Optional[house.Creative] = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[_ManifestWorker] = None
        self._network: Optional[QNetworkAccessManager] = None

        self.setObjectName("AdBanner")
        self.setProperty("role", "ad-banner")
        self.setFixedHeight(DEFAULT_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"""
            #AdBanner {{
                background: {palette.bg_surface};
                border: 1px solid {palette.border_hairline};
                border-radius: 10px;
            }}
            """
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(14)

        # Optional thumbnail
        self._thumb = QLabel()
        self._thumb.setFixedSize(72, 72)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet(
            f"background: {palette.bg_sunken}; "
            f"border: 1px solid {palette.border_soft}; "
            f"border-radius: 6px;"
        )
        self._thumb.setVisible(False)
        root.addWidget(self._thumb)

        # Centre column — sponsored eyebrow + headline + body
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self._eyebrow = QLabel("SPONSORED")
        self._eyebrow.setFont(typography.micro())
        self._eyebrow.setStyleSheet(
            f"color: {palette.text_tertiary}; letter-spacing: 1.6px;"
        )
        text_col.addWidget(self._eyebrow)

        self._headline = QLabel("Your fastest tune-up is one click away.")
        self._headline.setFont(typography.body_strong())
        self._headline.setStyleSheet(f"color: {palette.text_primary};")
        self._headline.setWordWrap(True)
        text_col.addWidget(self._headline)

        self._body = QLabel("Loading sponsor offers…")
        self._body.setFont(typography.small())
        self._body.setStyleSheet(f"color: {palette.text_secondary};")
        self._body.setWordWrap(True)
        text_col.addWidget(self._body)

        root.addLayout(text_col, stretch=1)

        # Right column — CTA button
        self._cta = QPushButton("Get deals")
        self._cta.setProperty("variant", "primary")
        self._cta.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cta.setMinimumWidth(140)
        self._cta.clicked.connect(self._on_click)
        root.addWidget(self._cta)

        # Bind config + initial state
        self.refresh()

    # ------------------------------------------------------------------ public
    def refresh(self) -> None:
        """Re-evaluate visibility from current config and reload creative."""
        if not self._config.ads_enabled:
            self.setVisible(False)
            return
        self.setVisible(True)
        self._kick_off_load()

    # ------------------------------------------------------------------ load
    def _kick_off_load(self) -> None:
        # Re-use a single background load at a time
        if self._thread is not None and self._thread.isRunning():
            return

        thread = QThread(self)
        worker = _ManifestWorker(self._config.ads_manifest_url)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.ready.connect(self._on_manifest)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_thread)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _clear_thread(self) -> None:
        self._thread = None
        self._worker = None

    def closeEvent(self, event) -> None:    # type: ignore[override]
        # If the worker is still mid-fetch when the widget is closed (e.g.
        # window closing before the first manifest comes back), wait briefly
        # so we don't trigger Qt's "QThread destroyed while running" warning.
        thread = self._thread
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(1500)
        super().closeEvent(event)

    def _on_manifest(self, manifest: house.Manifest) -> None:
        creative = manifest.pick_one()
        if creative is None:
            log.info("no active creatives in manifest")
            self.setVisible(False)
            return
        self._creative = creative
        self._render(creative)
        if creative.image_url:
            self._fetch_image_async(creative.image_url)

    def _render(self, c: house.Creative) -> None:
        self._eyebrow.setText(
            f"SPONSORED · {c.sponsor.upper()}" if c.sponsor else "SPONSORED"
        )
        self._headline.setText(c.headline)
        self._body.setText(c.body)
        self._cta.setText(c.cta or "Learn more")
        self._thumb.setVisible(False)  # shown again only if image loads

    # ------------------------------------------------------------------ image
    def _fetch_image_async(self, url: str) -> None:
        if self._network is None:
            self._network = QNetworkAccessManager(self)
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(
            b"User-Agent",
            b"GameBoost/2.1 (+https://gameboost.app)",
        )
        reply = self._network.get(request)
        reply.finished.connect(lambda r=reply: self._on_image_loaded(r))

    def _on_image_loaded(self, reply: QNetworkReply) -> None:
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                return
            data = bytes(reply.readAll())
            pix = QPixmap()
            if not pix.loadFromData(data):
                return
            self._thumb.setPixmap(
                pix.scaled(
                    72, 72,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self._thumb.setVisible(True)
        finally:
            reply.deleteLater()

    # ------------------------------------------------------------------ click
    def _on_click(self) -> None:
        creative = self._creative
        if creative is None:
            # No manifest yet — fall back to the configured sponsor URL.
            url = house.build_click_url(
                self._config.ads_sponsor_url,
                creative_id="default",
                slot=self._slot,
            )
        else:
            url = house.build_click_url(creative.click_url, creative.id, self._slot)
        log.info("ad click → %s", url)
        QDesktopServices.openUrl(QUrl(url))
