"""Generate the PNG tile assets required by the MSIX AppxManifest.

The Microsoft Store rejects an MSIX package that's missing any of the
declared visual assets, but we don't want to commit binary art to the
repo (it bloats the diff and locks us to a single design). Instead we
synthesise every tile from a vector recipe at build time, mirroring the
in-app ``BrandMark`` widget (hex frame + speed-cut diagonals + lime
lightning bolt + cyan rule).

Usage::

    python tools/build_msix_assets.py msix/Assets        # default
    python tools/build_msix_assets.py --force            # regenerate even
                                                          # if files exist

Run by ``.github/workflows/release.yml`` during the MSIX packaging
step. Pillow is the only runtime dependency.

Design rules
------------

* **Background** ``#0B0F19`` (obsidian).
* **Hex frame** ``#58D3FF`` cyan @ ~22 % alpha as the base ring; two
  arms (top-left and bottom-right) re-stroked at 100 % for the speed-cut
  silhouette.
* **Bolt** ``#A6FF00`` lime, the same six-point lightning shape used in
  the desktop sidebar.
* **Wordmark** is added on tiles where it actually reads:
    - ``Square150x150Logo`` and ``Square310x310Logo``
      — ``GAMEBOOSTAPEX`` under the bolt, ``APEX`` sub-label.
    - ``Wide310x150Logo`` and ``SplashScreen``
      — horizontal lockup, hex+bolt left, wordmark right.
  Smaller tiles (44, 50, 71) are icon-only because text would be
  illegible at those sizes.

Drop a hand-authored PNG with the same filename into ``msix/Assets/``
to override any of these tiles.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Brand palette — same hex values used by app/ui/theme/palette.py.
BACKGROUND = (11, 15, 25, 255)        # #0B0F19  obsidian
ACCENT_CYAN = (88, 211, 255, 255)     # #58D3FF
ACCENT_LIME = (166, 255, 0, 255)      # #A6FF00
TEXT_PRIMARY = (240, 244, 252, 255)   # #F0F4FC
BORDER_HAIRLINE = (88, 211, 255, 56)  # cyan @ 22 % alpha

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


def _load_font(size: int, *, weight: str = "bold") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Best-effort font loader: Segoe UI on Windows, fallback otherwise."""
    bold_candidates = [
        "C:/Windows/Fonts/seguibl.ttf",      # Segoe UI Black
        "C:/Windows/Fonts/segoeuib.ttf",     # Segoe UI Bold
        "C:/Windows/Fonts/arialbd.ttf",      # Arial Bold
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    regular_candidates = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    candidates = bold_candidates if weight == "bold" else regular_candidates
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _hex_polygon(cx: float, cy: float, radius: float) -> list[tuple[float, float]]:
    """Flat-top hexagon vertices around (cx, cy)."""
    return [
        (
            cx + radius * math.cos(math.radians(60 * i - 30)),
            cy + radius * math.sin(math.radians(60 * i - 30)),
        )
        for i in range(6)
    ]


def _bolt_path(cx: float, cy: float, s: float) -> list[tuple[float, float]]:
    """Six-point lightning bolt centred on (cx, cy), scaled to ``s``.

    Same geometry as ``app/ui/widgets/brand_mark.py``.
    """
    return [
        (cx + s * 0.05, cy - s),
        (cx - s * 0.55, cy + s * 0.10),
        (cx - s * 0.05, cy + s * 0.10),
        (cx - s * 0.20, cy + s),
        (cx + s * 0.55, cy - s * 0.10),
        (cx + s * 0.10, cy - s * 0.10),
    ]


def _draw_hex_bolt(draw: ImageDraw.ImageDraw, cx: float, cy: float, size: float) -> None:
    """Render the hex-frame + lightning-bolt mark centred on (cx, cy).

    ``size`` is the diameter of the hex circumscribed circle.
    """
    radius = size / 2
    pts = _hex_polygon(cx, cy, radius)

    # Faint full hex outline (cyan @ low alpha).
    line_w = max(1, int(round(size * 0.045)))
    draw.polygon(pts, outline=BORDER_HAIRLINE, fill=None)

    # Speed-cut: re-stroke the top-left and bottom-right arms at full alpha.
    accent_w = max(2, int(round(size * 0.06)))
    draw.line([pts[0], pts[1]], fill=ACCENT_CYAN, width=accent_w)
    draw.line([pts[3], pts[4]], fill=ACCENT_CYAN, width=accent_w)

    # Lightning bolt in lime.
    bolt_scale = size * 0.42
    bolt = _bolt_path(cx, cy, bolt_scale)
    draw.polygon(bolt, fill=ACCENT_LIME)


def _render_square(width: int, height: int, *, with_text: bool) -> Image.Image:
    img = Image.new("RGBA", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(img)

    # Reserve ~22 % of the height for the wordmark when present.
    available_h = height * 0.74 if with_text else height
    glyph_size = min(width, available_h) * 0.78
    cx = width / 2
    cy = (available_h / 2) if with_text else (height / 2)
    _draw_hex_bolt(draw, cx, cy, glyph_size)

    if with_text:
        # "GAMEBOOSTAPEX" under the mark.
        font_size = max(10, int(round(width * 0.078)))
        font = _load_font(font_size, weight="bold")
        text = "GAMEBOOSTAPEX"
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = (width - tw) // 2 - bbox[0]
        ty = int(available_h + (height - available_h - th) // 2 - bbox[1] - 4)
        draw.text((tx, ty), text, font=font, fill=TEXT_PRIMARY)

        # Cyan hairline rule under the wordmark.
        rule_y = ty + th + 4
        rule_w = int(width * 0.32)
        draw.line(
            [((width - rule_w) // 2, rule_y), ((width + rule_w) // 2, rule_y)],
            fill=ACCENT_CYAN,
            width=1,
        )

    return img


def _render_horizontal(width: int, height: int) -> Image.Image:
    """Wide tile / splash: hex+bolt on the left, wordmark on the right."""
    img = Image.new("RGBA", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(img)

    # Mark sits in the left ~38 % of the canvas.
    glyph_size = min(height * 0.78, width * 0.30)
    mark_cx = width * 0.22
    mark_cy = height / 2
    _draw_hex_bolt(draw, mark_cx, mark_cy, glyph_size)

    # Wordmark to the right of the mark.
    text_x_start = mark_cx + glyph_size / 2 + max(12, width * 0.04)

    title_size = max(16, int(round(height * 0.30)))
    title_font = _load_font(title_size, weight="bold")
    title = "GAMEBOOSTAPEX"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    title_h = bbox[3] - bbox[1]
    draw.text(
        (text_x_start - bbox[0], mark_cy - title_h // 2 - bbox[1] - height * 0.05),
        title,
        font=title_font,
        fill=TEXT_PRIMARY,
    )

    # Sub-label "APEX" in cyan, tracked.
    sub_size = max(10, int(round(height * 0.13)))
    sub_font = _load_font(sub_size, weight="bold")
    sub = "PERFORMANCE TUNER FOR GAMERS"
    sbbox = draw.textbbox((0, 0), sub, font=sub_font)
    draw.text(
        (text_x_start - sbbox[0], mark_cy + height * 0.05 - sbbox[1]),
        sub,
        font=sub_font,
        fill=ACCENT_CYAN,
    )

    return img


def _render_tile(name: str, width: int, height: int) -> Image.Image:
    # Smallest icons: glyph-only, no text.
    if width <= 71 or name == "StoreLogo.png":
        return _render_square(width, height, with_text=False)
    # Wide tile + splash: horizontal lockup.
    if width != height:
        return _render_horizontal(width, height)
    # Larger squares: glyph + wordmark.
    return _render_square(width, height, with_text=True)


def main(out_dir: str, *, force: bool = False) -> int:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    for name, w, h in TILES:
        dst = target / name
        if dst.exists() and not force:
            print(f"[skip] {dst} already exists (user-provided), keeping it")
            continue
        img = _render_tile(name, w, h)
        img.save(dst, format="PNG", optimize=True)
        print(f"[ok]   wrote {dst} ({w}x{h})")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "out", nargs="?", default="msix/Assets",
        help="output directory (default ./msix/Assets)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="regenerate every tile, even if a file already exists",
    )
    ns = parser.parse_args()
    sys.exit(main(ns.out, force=ns.force))
