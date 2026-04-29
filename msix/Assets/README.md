# MSIX visual assets

This directory holds the PNG tiles referenced by `../AppxManifest.xml`.
At release time, `tools/build_msix_assets.py` generates any missing
files here using the brand palette (deep navy + cyan accent, "GB"
wordmark). Drop a real PNG with the same filename to override.

## Required filenames

| Filename | Size | Used by |
| -------- | ---- | ------- |
| `StoreLogo.png` | 50 × 50 | Store listing thumbnail |
| `Square44x44Logo.png` | 44 × 44 | Taskbar / window icon |
| `Square71x71Logo.png` | 71 × 71 | Small Start Menu tile |
| `Square150x150Logo.png` | 150 × 150 | Default Start Menu tile |
| `Square310x310Logo.png` | 310 × 310 | Large Start Menu tile |
| `Wide310x150Logo.png` | 310 × 150 | Wide Start Menu tile |
| `SplashScreen.png` | 620 × 300 | Launch splash |

The auto-generated tiles are deliberately minimal so the build never
fails on missing assets. Replace them with a real logo before the next
Microsoft Store submission.
