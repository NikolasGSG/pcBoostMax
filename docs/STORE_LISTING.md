# Microsoft Store Listing — GameBoostApex

Drop-in copy for Partner Center → Store listings → English (United States).
Every section is sized to its Partner Center field limit and avoids
language Microsoft commonly rejects (no "best", no "amazing", no
unsubstantiated speed claims, no competitor mentions).

---

## Display name

```
GameBoostApex
```

## Short title (limit 50)

```
Transparent Windows tuner for gamers
```

## Sort title (limit 255 — same as display unless you need alphabetisation)

```
GameBoostApex
```

## Voice title (optional, used by Cortana — leave blank or repeat display)

```
GameBoostApex
```

---

## Short description (limit 200, ideal 140-160)

```
A transparent, fully reversible Windows tuner for gamers. Every change is explained, logged, and one click away from rollback. 100% local. No accounts, no telemetry.
```

(159 chars)

---

## Description (limit 10,000)

```
GameBoostApex is a Windows performance tuner for PC gamers who want to know exactly what their optimizer is doing. Every setting it touches is explained in plain language, recorded in an action history, and reversible from a single Safety tab — including a one-click rollback of every change you ever applied.

WHAT IT TUNES

GameBoostApex ships seventeen curated optimization rules covering the parts of Windows that actually matter when you sit down to play:

  • Power plans — switch to High Performance or Ultimate Performance for the session
  • CPU — disable core parking, pin minimum CPU state to 100%, raise NT timer resolution to 0.5 ms
  • GPU — enable Hardware-accelerated GPU Scheduling (HAGS), disable DWM fullscreen optimizations system-wide
  • Network — disable Nagle's algorithm on every NIC for lower input-to-server latency
  • Telemetry & background services — disable SysMain, Windows Search and DiagTrack while you play
  • Visual effects — switch Windows to "Best performance"
  • Background apps & Game DVR — suspend (not kill) heavy background processes for the session

Every rule has four properties shown directly on the card: WHAT it does, WHY it matters for gaming, its RISK level, and whether it is reversible. Nothing is applied without an explicit click on Apply and a confirmation dialog listing the action count.

AUTOPILOT — HANDS-FREE TUNING

Once enabled, AutoPilot quietly applies the safe rules of the Recommended preset on boot (max once per day), activates per-game profiles when a game launches, and resolves curated critical insights without prompts. Everything stays reversible from the Safety tab.

GAME HUB

GameBoostApex scans your installed library across Steam, Epic Games, GOG Galaxy, Battle.net, Riot Client and Xbox automatically. Every detected title appears in a fast cached grid with launcher chips, search, filter by launcher, sort by recently played, and Play / Tune actions on every tile.

PER-GAME PROFILES

Each game can have its own profile: power plan, process priority, CPU affinity, a list of background apps to suspend for the duration of the session, and an automatic baseline restore on exit. Profiles are stored as plain JSON under %LOCALAPPDATA%\GameBoostApexOptimizer\game_profiles\, so they are inspectable and portable.

LIVE DASHBOARD

A permanent header ticker shows CPU, RAM, GPU, Disk and Network with per-metric pressure colouring. The Dashboard view adds large readouts for each subsystem, a readiness gauge for your hardware, and an automatically surfaced bottleneck list (e.g. "GPU is 17% over its thermal target", "drive C: is 96% full and fragmented").

REAL FPS PANEL

The Monitor tab includes a real frame-rate panel with average FPS, 1% low, 0.1% low, frame time and a rolling frame-time graph. When PresentMon.exe is on PATH (or dropped next to the binary) the panel uses true per-process FPS; otherwise it falls back to a Windows GPU-engine activity proxy. No vendor SDK is required.

IN-GAME HUD OVERLAY

A frameless, always-on-top panel shows live FPS, frame time, CPU / GPU / RAM / NET / DISK and the foreground process. Click-through mode, drag-to-anywhere positioning, configurable layout, per-user global hotkey (default Ctrl+Shift+F12).

CLEANUP, INSIGHTS & TOOLS

  • Cleanup — transparent, preview-first disk cleanup. Every file is shown, grouped by category, before anything is deleted.
  • Insights — an auto-troubleshooter that reads your system and surfaces curated findings (driver mismatches, thermal throttling, fragmented disks, missing power options).
  • Tools — process hunter, DNS benchmark, ping tester, hardware findings dump, daily report, lightweight macros.

SAFETY MODEL

Every reversible action stores a backup payload before it runs. The Safety tab lists every action with its status (applied / rolled back / failed) and exposes a one-click rollback for any reversible entry. You can also create a Windows System Restore point before the first apply.

PRIVACY

GameBoostApex runs entirely on your machine. There are no accounts, no analytics SDKs inside the binary, no third-party JavaScript, and no background telemetry. The app is ads-supported through a small banner that links out to a separately hosted sponsor page; the desktop binary itself never loads ads or trackers. Full details: https://nikolasgsg.github.io/pcBoostMax/privacy.html

REQUIREMENTS

  • Windows 10 1909 or later, or Windows 11
  • x64 processor
  • 200 MB free disk space
  • Some optimizations require an Administrator confirmation prompt the first time you apply them
```

(approx 4,300 chars, leaves headroom for future expansion)

---

## What's new in this version (limit 1,500)

```
v2.1.4 — Rebrand to GameBoostApex.

  • Brand refresh across the entire UI, installer and Microsoft Store package.
  • Microsoft Store package (MSIX) now produced alongside the portable EXE and Inno Setup installer.
  • Fix: FPS panel rows no longer overlap on high-DPI displays — switched to QGridLayout with hard row-height caps.
  • Fix: MSIX manifest XML validation error caused by an illegal "--" sequence in a comment header.
  • Internal: rebuilt CI mirror so /downloads/GameBoostApex-latest-* always points at the latest release. No more stale URLs after a re-tag.
```

---

## Product features (limit 200 each, max 20 — Microsoft shows these as bullet points right under the screenshots)

```
1. 17 curated optimization rules. Each shows what it does, why it matters for gaming, its risk level, and whether it is reversible.
2. AutoPilot applies the Recommended preset on boot, swaps to per-game profiles when a game starts, and resolves insights without prompts.
3. Game Hub auto-detects Steam, Epic, GOG, Battle.net, Riot and Xbox libraries. Single launch grid with per-game tuning profiles.
4. Per-game profiles cover power plan, process priority, CPU affinity, background-app suspension and an automatic baseline restore on exit.
5. Live dashboard with real-time CPU, RAM, Disk and Network cards, hardware readiness gauge and surfaced bottlenecks.
6. Real FPS panel with average, 1% low, 0.1% low, frame time and frame-time graph. PresentMon support for true per-process FPS.
7. In-game HUD overlay with click-through mode, draggable position, configurable layout and a user-defined global hotkey.
8. Live HUD ticker pinned to the top of the window for CPU, RAM, GPU, Disk and Network with per-metric pressure colouring.
9. Preview-first Cleanup. Every file is shown grouped by category before any deletion. No silent disk operations.
10. Safety tab with action history, per-action backup, optional Windows System Restore point and one-click rollback.
11. Insights auto-troubleshooter surfaces driver issues, throttling, fragmented disks and missing power options.
12. Tools include a process hunter, DNS benchmark, ping tester, hardware findings dump and lightweight macros.
13. 100% local. No accounts, no analytics SDKs in the binary, no third-party JavaScript, no telemetry.
```

(13 features, each well under 200 chars. Add more as the product grows.)

---

## Search terms (limit 7 entries, 30 chars each)

```
pc tuner
windows optimizer
game booster
fps booster
gaming optimizer
ram cleaner
performance monitor
```

---

## Copyright and trademark info (limit 200)

```
© 2026 Nikolas Gudmundsen. Open-source under the MIT license. Windows is a trademark of Microsoft Corporation.
```

---

## Additional license terms (optional — leave blank to use the default Standard EULA)

Leave blank. The Standard Application License Terms shown in Partner
Center are sufficient. Source-availability is communicated via the
description and the GitHub link.

---

## URLs

| Field            | URL                                                                |
| ---------------- | ------------------------------------------------------------------ |
| Privacy policy   | `https://nikolasgsg.github.io/pcBoostMax/privacy.html`             |
| Support contact  | `https://github.com/NikolasGSG/pcBoostMax/issues`                  |
| Website          | `https://nikolasgsg.github.io/pcBoostMax/`                         |

---

## Category & sub-category

```
Category:     Utilities & tools
Subcategory:  Personalization
```

(Or pick **Developer tools → Utilities** if Microsoft's reviewer
classifies utilities differently for your account region. Both
work — the listing is identical.)

---

## Age rating (IARC)

Run the IARC questionnaire and answer **No** to every content
question. The product contains no violence, profanity, gambling,
in-app purchases, location collection or user-generated content.
You will receive a free **3+ / Everyone / PEGI 3** rating in 24 hours.

---

## Pricing & availability

```
Price model:        Free
Markets:            All available markets
Visibility:         Public
Schedule:           Release as soon as published
Org licensing:      Allow purchase by anyone (default)
Discoverability:    "Make this product available and discoverable" (default)
```

---

## Screenshots — capture checklist

Microsoft accepts 1-9 screenshots, minimum 1366×768 (landscape) or
768×1366 (portrait), PNG/JPG, max 8 MB each. Capture them at
**1920×1080** for crispness on every display.

Recommended set in submission order — the first two are the most
important; Microsoft's Store surface uses them as social previews.

  1. **Dashboard** — full window. Live ticker visible. At least one
     bottleneck card surfaced.
  2. **Game Hub** — full window. Grid populated with at least 6 game
     tiles spread across different launchers.
  3. **Optimize view** — rules list expanded, two or three toggles
     visible, the "Apply 5 actions" CTA at the bottom.
  4. **Monitor — FPS panel** — frame-time graph populated with at
     least ~30 seconds of history.
  5. **In-game HUD overlay** — captured over a real game (e.g. CS2,
     Apex, anything fullscreen-borderless). Show the HUD with all
     metrics enabled.
  6. **Safety tab** — action history with at least one applied + one
     rolled-back row.
  7. **Cleanup preview** — files grouped by category, "Will free
     X.Y GB" footer visible.
  8. *(optional)* **AutoPilot settings** — toggle on, with the
     "Applied 12 rules at 09:14 today" status line visible.
  9. *(optional)* **Insights tab** — three or four findings cards,
     each showing severity colour and a suggested action.

### Capturing them

Easiest: run the app at full window, **Win + Shift + S → Window**,
save as PNG. Size each export to **1920×1080** (Snipping Tool can crop
+ resize, or use IrfanView's File → Batch Conversion).

Or build a one-shot capture script — see `tools/capture_store_shots.py`
(create if not present) that iterates every view via the existing
QApplication and saves a PNG per view.

---

## Submission checklist

Before clicking **Submit to Store**, verify:

  - [ ] **Packages** page lists `https://nikolasgsg.github.io/pcBoostMax/downloads/GameBoostApex-2.1.4-x64.msix`
  - [ ] **Properties** → Category set, system requirements ticked
  - [ ] **Age ratings** → IARC questionnaire complete (3+/Everyone)
  - [ ] **Pricing and availability** → Free, all markets, public
  - [ ] **Store listing (English)** → display name, short description, description, what's new, 13 features, copyright, search terms
  - [ ] **Screenshots** → at least 4 (Microsoft minimum is 1, but 4-6 dramatically improves conversion)
  - [ ] **Store logo** — already inside the MSIX (`Assets/StoreLogo.png`), Microsoft pulls it automatically. No manual upload needed.

Hit **Submit to Store**. Certification typically lands in 24-72 h.
