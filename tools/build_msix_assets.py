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
    python tools/build_msix_assets.py --marketing        # ALSO emit optional
                                                          # Store-listing logos
                                                          # (720x1080, 1080x1080,
                                                          # 2400x1200) into
                                                          # ./marketing_assets/

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

# Optional Store-listing images used by Partner Center → Store listings →
# Store logos. NOT referenced by AppxManifest — they live outside the
# MSIX so we keep them in a separate output folder.
#
# Microsoft uses these on featured-app surfaces (start carousel,
# spotlight cards, themed lists). 9:16 is the most commonly surfaced.
MARKETING_TILES: list[tuple[str, int, int]] = [
    ("StoreLogo_720x1080.png", 720, 1080),     # 9:16  — featured carousel
    ("StoreLogo_1080x1080.png", 1080, 1080),   # 1:1   — spotlight tile
    ("StoreLogo_2400x1200.png", 2400, 1200),   # 23:10 — wide hero (logo only)
    ("HeroImage_1920x1080.png", 1920, 1080),   # 16:9  — 'Super hero art'
                                                #         editorial layout
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

    # Cyan rule under the wordmark.
    rule_y = mark_cy + height * 0.05 + title_h + max(8, int(width * 0.012))
    rule_w = int(width * 0.36)
    draw.line(
        [((width - rule_w) // 2, rule_y), ((width + rule_w) // 2, rule_y)],
        fill=ACCENT_CYAN,
        width=max(1, int(width * 0.003)),
    )

    # Sub-label "APEX" in cyan, tracked.
    sub_size = max(10, int(round(height * 0.13)))
    sub_font = _load_font(sub_size, weight="bold")
    sub = "PERFORMANCE TUNER FOR GAMERS"
    sbbox = draw.textbbox((0, 0), sub, font=sub_font)
    draw.text(
        (text_x_start - sbbox[0], rule_y + max(16, int(width * 0.020))),
        sub,
        font=sub_font,
        fill=ACCENT_CYAN,
    )

    return img


def _render_portrait(width: int, height: int) -> Image.Image:
    """Tall poster lockup: big hex+bolt up top, wordmark + tagline below.

    Used for the optional Microsoft Store 720x1080 / 1080x1080 logos
    that appear on featured-app surfaces.
    """
    img = Image.new("RGBA", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(img)

    # Subtle radial vignette so the centre reads brighter and the corners
    # gently fade to true obsidian. Done by stamping a few transparent
    # ellipses at low alpha — cheap and looks editorial.
    for r_factor, alpha in ((0.55, 16), (0.40, 14), (0.28, 10)):
        rx = int(width * r_factor)
        ry = int(height * r_factor * 0.55)
        cx, cy = width // 2, int(height * 0.42)
        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        gdraw.ellipse(
            [(cx - rx, cy - ry), (cx + rx, cy + ry)],
            fill=(88, 211, 255, alpha),
        )
        img.alpha_composite(glow)
    draw = ImageDraw.Draw(img)

    # ---- Hex+bolt mark in the upper third -----------------------------
    glyph_size = int(min(width * 0.48, height * 0.32))
    mark_cx = width / 2
    mark_cy = height * 0.32
    _draw_hex_bolt(draw, mark_cx, mark_cy, glyph_size)

    # ---- Wordmark below the mark --------------------------------------
    title_size = max(28, int(round(width * 0.085)))
    title_font = _load_font(title_size, weight="bold")
    title = "GAMEBOOSTAPEX"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    title_y = int(height * 0.56)
    title_x = (width - tw) // 2 - bbox[0]
    draw.text((title_x, title_y - bbox[1]), title, font=title_font, fill=TEXT_PRIMARY)

    # Cyan rule under the wordmark.
    rule_y = title_y + th + max(8, int(width * 0.012))
    rule_w = int(width * 0.36)
    draw.line(
        [((width - rule_w) // 2, rule_y), ((width + rule_w) // 2, rule_y)],
        fill=ACCENT_CYAN,
        width=max(1, int(width * 0.003)),
    )

    # ---- Tagline ------------------------------------------------------
    tag_size = max(14, int(round(width * 0.030)))
    tag_font = _load_font(tag_size, weight="bold")
    tagline = "PERFORMANCE TUNER FOR GAMERS"
    tbbox = draw.textbbox((0, 0), tagline, font=tag_font)
    ttw = tbbox[2] - tbbox[0]
    tag_y = rule_y + max(16, int(width * 0.020))
    draw.text(
        ((width - ttw) // 2 - tbbox[0], tag_y - tbbox[1]),
        tagline,
        font=tag_font,
        fill=ACCENT_CYAN,
    )

    return img


def _render_hero(width: int, height: int) -> Image.Image:
    """Microsoft Store 'Super hero art' (1920x1080) editorial layout.

    Differs from the simple horizontal lockup by adding:

      * a faint hex-grid pattern across the entire canvas,
      * a soft cyan radial glow centred on where the mark sits,
      * an oversized hex+bolt on the left,
      * a big bold headline + cyan rule + tagline on the right.

    This is what Microsoft surfaces on the Store homepage's
    Featured Apps carousel and in themed category panels.
    """
    img = Image.new("RGBA", (width, height), BACKGROUND)

    # ---- Layer 1: faint hex-grid pattern --------------------------------
    # Drawn into a separate RGBA layer at very low alpha so the obsidian
    # background still dominates and the eye doesn't catch the pattern
    # consciously — it just adds texture.
    pattern = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pattern)
    spacing = max(48, width // 28)
    radius = spacing * 0.46
    grid_color = (88, 211, 255, 16)   # cyan @ ~6 % alpha
    rows = int(height / (spacing * 0.866)) + 2
    cols = int(width / spacing) + 2
    for row in range(-1, rows):
        for col in range(-1, cols):
            cx = col * spacing + (spacing / 2 if row % 2 else 0)
            cy = row * spacing * 0.866
            pdraw.polygon(_hex_polygon(cx, cy, radius), outline=grid_color, fill=None)
    img.alpha_composite(pattern)

    # ---- Layer 2: soft cyan radial glow centred on the mark ------------
    for r_factor, alpha in ((0.65, 32), (0.45, 24), (0.28, 18)):
        rx = int(width * r_factor * 0.55)
        ry = int(height * r_factor)
        gx = int(width * 0.28)
        gy = height // 2
        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        gdraw.ellipse([(gx - rx, gy - ry), (gx + rx, gy + ry)], fill=(88, 211, 255, alpha))
        img.alpha_composite(glow)

    draw = ImageDraw.Draw(img)

    # ---- Layer 3: oversized hex+bolt on the left -----------------------
    glyph_size = int(min(height * 0.62, width * 0.30))
    mark_cx = width * 0.26
    mark_cy = height / 2
    _draw_hex_bolt(draw, mark_cx, mark_cy, glyph_size)

    # ---- Layer 4: editorial typography on the right --------------------
    text_x = mark_cx + glyph_size / 2 + width * 0.04

    title_size = max(48, int(round(height * 0.135)))
    title_font = _load_font(title_size, weight="bold")
    title = "GAMEBOOSTAPEX"
    tbbox = draw.textbbox((0, 0), title, font=title_font)
    title_w = tbbox[2] - tbbox[0]
    title_h = tbbox[3] - tbbox[1]
    # Anchor the headline above the vertical centre so the rule + subhead
    # sit comfortably below it.
    title_y = int(mark_cy - title_h - height * 0.04)
    draw.text((text_x - tbbox[0], title_y - tbbox[1]), title, font=title_font, fill=TEXT_PRIMARY)

    # Cyan accent rule under the headline. Width matches roughly a third
    # of the headline so it reads as an editorial under-bar, not a list
    # divider.
    rule_y = int(title_y + title_h + max(10, height * 0.014))
    rule_w = int(min(title_w * 0.36, width * 0.18))
    draw.line(
        [(text_x, rule_y), (text_x + rule_w, rule_y)],
        fill=ACCENT_CYAN,
        width=max(2, int(height * 0.005)),
    )

    # Tagline / subhead in cyan.
    sub_size = max(20, int(round(height * 0.045)))
    sub_font = _load_font(sub_size, weight="bold")
    sub = "TUNE WINDOWS FOR THE GAME IN FRONT OF YOU"
    sbbox = draw.textbbox((0, 0), sub, font=sub_font)
    sub_y = int(rule_y + max(20, height * 0.025))
    draw.text((text_x - sbbox[0], sub_y - sbbox[1]), sub, font=sub_font, fill=ACCENT_CYAN)

    # Tertiary feature ticker centred along the bottom edge in muted
    # cyan. Anchors the composition and gives the reviewer something
    # specific to read.
    ticker_size = max(14, int(round(height * 0.024)))
    ticker_font = _load_font(ticker_size, weight="bold")
    ticker = "POWER  ·  CPU  ·  GPU  ·  NETWORK  ·  TELEMETRY  ·  SAFETY"
    kbbox = draw.textbbox((0, 0), ticker, font=ticker_font)
    ktw = kbbox[2] - kbbox[0]
    ticker_y = int(height - height * 0.07 - kbbox[3])
    draw.text(
        ((width - ktw) // 2 - kbbox[0], ticker_y - kbbox[1]),
        ticker,
        font=ticker_font,
        fill=(60, 145, 175, 255),     # muted cyan so it doesn't compete
    )

    return img


def _render_marketing(name: str, width: int, height: int) -> Image.Image:
    """Dispatch to the right layout for marketing-only tiles."""
    if name.startswith("HeroImage"):
        return _render_hero(width, height)
    aspect = width / height
    # Tall poster (9:16) and square (1:1) both look right with the
    # vertical lockup — text reads top-to-bottom in either case.
    if aspect <= 1.05:
        return _render_portrait(width, height)
    # Wide hero (23:10): use the horizontal lockup so the wordmark sits
    # to the right of the mark.
    return _render_horizontal(width, height)


def _render_tile(name: str, width: int, height: int) -> Image.Image:
    # Smallest icons: glyph-only, no text.
    if width <= 71 or name == "StoreLogo.png":
        return _render_square(width, height, with_text=False)
    # Wide tile + splash: horizontal lockup.
    if width != height:
        return _render_horizontal(width, height)
    # Larger squares: glyph + wordmark.
    return _render_square(width, height, with_text=True)


def main(
    out_dir: str,
    *,
    force: bool = False,
    marketing: bool = False,
    marketing_dir: str = "marketing_assets",
) -> int:
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

    if marketing:
        mtarget = Path(marketing_dir)
        mtarget.mkdir(parents=True, exist_ok=True)
        for name, w, h in MARKETING_TILES:
            dst = mtarget / name
            if dst.exists() and not force:
                print(f"[skip] {dst} already exists, keeping it")
                continue
            img = _render_marketing(name, w, h)
            img.save(dst, format="PNG", optimize=True)
            print(f"[ok]   wrote {dst} ({w}x{h})")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "out", nargs="?", default="msix/Assets",
        help="output directory for MSIX tiles (default ./msix/Assets)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="regenerate every tile, even if a file already exists",
    )
    parser.add_argument(
        "--marketing", action="store_true",
        help="also emit optional 720x1080 / 1080x1080 / 2400x1200 "
             "Store-listing logos into ./marketing_assets/",
    )
    parser.add_argument(
        "--marketing-out", default="marketing_assets",
        help="output directory for marketing tiles (default ./marketing_assets)",
    )
    ns = parser.parse_args()
    sys.exit(main(ns.out, force=ns.force, marketing=ns.marketing, marketing_dir=ns.marketing_out))
