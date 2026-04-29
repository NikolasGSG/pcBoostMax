"""Generate the PNG tile assets required by the MSIX AppxManifest.

The Microsoft Store rejects an MSIX package that's missing any of the
declared visual assets, but we don't want to commit binary art to the
repo (it bloats the diff and locks us to a single design). Instead we
synthesise the assets from a vector recipe at build time.

The output is a flat colour tile with the wordmark "GB" centred. It's
deliberately minimal — once the user supplies a real logo we just drop
PNGs with the same names into ``msix/Assets/`` and this script becomes
a no-op.

Usage::

    python tools/build_msix_assets.py msix/Assets

Run by .github/workflows/release.yml during the MSIX packaging step.
Pillow is the only dependency (already required by the rest of the
release pipeline for screenshot rendering).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Brand palette — matches the desktop app's accent colour (cyan on near-black).
BACKGROUND = (11, 15, 25, 255)        # #0B0F19
ACCENT = (88, 211, 255, 255)          # #58D3FF
TEXT = (240, 244, 252, 255)           # near-white

# (filename, width, height) — every one of these is referenced by AppxManifest.
TILES: list[tuple[str, int, int]] = [
    ("StoreLogo.png", 50, 50),
    ("Square44x44Logo.png", 44, 44),
    ("Square71x71Logo.png", 71, 71),
    ("Square150x150Logo.png", 150, 150),
    ("Square310x310Logo.png", 310, 310),
    ("Wide310x150Logo.png", 310, 150),
    ("SplashScreen.png", 620, 300),
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Best-effort font loader: Segoe UI Bold on Windows, fallback otherwise."""
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/seguibl.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _render_tile(width: int, height: int, label: str = "GB") -> Image.Image:
    img = Image.new("RGBA", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(img)

    # Subtle accent corner stripe so the tile reads as a "real" app icon
    # rather than a debug rectangle. Drawn at 45° from the top-right corner.
    stripe_w = max(2, width // 24)
    for offset in range(stripe_w):
        draw.line(
            [(width - offset, 0), (width, offset)],
            fill=ACCENT,
            width=1,
        )

    # Wordmark — sized to ~55% of the shorter edge.
    short = min(width, height)
    font = _load_font(int(short * 0.55))
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    # textbbox returns the actual glyph box, but text() places the cursor at
    # the top-left ascender; correct for the bbox offset so the glyph is
    # truly centred.
    cx = (width - tw) // 2 - bbox[0]
    cy = (height - th) // 2 - bbox[1]
    draw.text((cx, cy), label, font=font, fill=TEXT)
    return img


def main(out_dir: str) -> int:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    for name, w, h in TILES:
        dst = target / name
        if dst.exists():
            print(f"[skip] {dst} already exists (user-provided), keeping it")
            continue
        img = _render_tile(w, h)
        img.save(dst, format="PNG", optimize=True)
        print(f"[ok]   wrote {dst} ({w}x{h})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "msix/Assets"))
