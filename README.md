# GameBoostApex

[![Release](https://img.shields.io/github/v/release/NikolasGSG/pcBoostMax?style=flat-square&color=A6FF00&label=download)](https://github.com/NikolasGSG/pcBoostMax/releases/latest)
[![CI](https://img.shields.io/github/actions/workflow/status/NikolasGSG/pcBoostMax/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/NikolasGSG/pcBoostMax/actions/workflows/ci.yml)
[![Downloads](https://img.shields.io/github/downloads/NikolasGSG/pcBoostMax/total?style=flat-square&color=00E4FF&label=downloads)](https://github.com/NikolasGSG/pcBoostMax/releases)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4?style=flat-square)](https://github.com/NikolasGSG/pcBoostMax/releases/latest)
[![Licence](https://img.shields.io/badge/licence-Proprietary-7E8C9F?style=flat-square)](LICENSE)
[![Privacy](https://img.shields.io/badge/privacy-PRIVACY.md-B070FF?style=flat-square)](PRIVACY.md)

**A safe, transparent PC tuner and gaming hub for Windows — built on PyQt6.**

▶ **[Download for Windows ↓](https://github.com/NikolasGSG/pcBoostMax/releases/latest)** &nbsp;·&nbsp; [Project site](https://NikolasGSG.github.io/pcBoostMax/) &nbsp;·&nbsp; [Privacy](PRIVACY.md) &nbsp;·&nbsp; [Changelog](CHANGELOG.md)

GameBoostApex is the v2.x rewrite of GameBoostApex Optimizer. It now bundles:

- a curated, fully reversible **Optimization Engine** (17+ rules with `what` / `why` / risk metadata),
- a hands-free **AutoPilot** that silently applies the safe Recommended preset, swaps to per-game profiles when a game starts, and resolves critical insights for you,
- a **Game Hub** that scans Steam / Epic / GOG / Battle.net / Riot / Xbox automatically, lets you launch any title from a single grid, and stores per-game tuning profiles,
- new v2.1 **Insights / Stats / Tools** tabs (auto-troubleshooter, hardware findings, daily reports, process hunter, DNS benchmark, ping tester, macros),
- a **live FPS panel** with average / 1% low / 0.1% low and frame-time graph (PresentMon when available, GPU-activity proxy otherwise),
- an always-on **HUD ticker** across the top of the window for CPU / RAM / GPU / Disk / Network,
- and the same in-game overlay, Cleanup, Safety, and Monitor tools that shipped in 1.x.

**No accounts. No analytics SDKs. No third-party JavaScript inside the binary.** The app is ads-supported (read [PRIVACY.md](PRIVACY.md) and [docs/MONETIZATION_HOWTO.md](docs/MONETIZATION_HOWTO.md) for the full picture).

---

## What's new in 2.0 — "APEX"

- **AutoPilot** — silent, hands-free automation. Once enabled, GameBoostApex applies the safe rules of the Recommended preset on boot (max once per day), activates per-game profiles when a game launches, and resolves curated critical insights without prompts. Everything stays reversible from the Safety tab.
- **Per-game profiles** — swap power plan, set process priority and CPU affinity, suspend a list of background apps for the duration of the session, and restore baseline on exit. Stored as JSON under `%LOCALAPPDATA%/GameBoostApexOptimizer/game_profiles/`.
- **Game Hub view** — fast, cached library grid with launcher chips, search, filter by launcher, sort by recently played, and "Play" / "Tune" actions on every tile.
- **Real FPS panel** in Monitor — large mono FPS readout with average, 1% low, 0.1% low, frame time, and a frame-time graph.
- **Live HUD ticker** — a permanent strip across the top of the window showing CPU / RAM / GPU / Disk / Network with per-metric pressure colouring.
- **APEX visual identity** — obsidian black + lime/cyan palette, condensed display type, monospaced numerics, hex-grid backdrops, lime corner brackets and a custom-painted hex-bolt brand mark. No stock widgets pretending to be modern.

---

## Highlights

- **Live Dashboard** — real-time CPU / RAM / Disk / Network cards, a readiness
  gauge, hardware spec summary, and automatically-surfaced bottlenecks.
- **Optimization Engine** — 17 curated, declarative rules (baseline + the
  "Unleash" pack). Each rule explains *what it does*, *why it matters for
  gaming*, its *risk level*, and whether it is reversible.
  - *Baseline:* High-Performance power plan, Visual Effects, Game DVR,
    Background apps, Startup programs, Temp cleanup.
  - *Unleash pack:* Ultimate Performance power plan, disable CPU core
    parking, pin minimum CPU state to 100%, enable Hardware-accelerated
    GPU Scheduling (HAGS), disable DWM fullscreen optimizations system-wide,
    disable SysMain / Windows Search / DiagTrack, disable Nagle's algorithm
    for every NIC, "Best performance" visual effects, raise NT timer
    resolution to 0.5 ms.
- **Game Mode** — one-tap session preset: switches to High Performance, trims
  animations, disables Game DVR background recording, and can *suspend*
  (not kill) heavy background apps. Fully restored on deactivation.
- **In-Game Overlay (HUD)** — frameless always-on-top panel showing live FPS,
  frame time, CPU / GPU / RAM / NET / DISK utilisation and the foreground
  process. Click-through mode, draggable, configurable layout, per-user
  global hotkey (default `Ctrl+Shift+F12`). Uses Windows GPU Engine
  performance counters — no vendor SDK required. Drop `PresentMon.exe` next
  to the app (or put it on `PATH`) to get true per-process FPS; otherwise
  the HUD shows a GPU-activity proxy.
- **Cleanup** — transparent, preview-first disk cleanup. Every file is shown
  grouped by category before anything is deleted.
- **Safety-first** — optional Windows System Restore point, per-action
  backups, action history log, and one-click rollback of any reversible
  change.
- **Zero-dependency UI** — the entire visual design (sidebar, ring gauge,
  live graphs, toggle switches, action cards, badges, banners, hero card,
  icons) is painted custom on top of QPainter. No component libraries, no
  stock widget overrides pretending to be modern.

---

## Architecture

```
┌─────────────────────── main.py (entry) ───────────────────────┐
│                                                               │
│   ┌───────────────── AppController ─────────────────┐         │
│   │   EventBus · AppConfig · Logger                  │         │
│   │   HardwareDetector · PerformanceMonitor          │         │
│   │   BottleneckAnalyzer · CleanupService            │         │
│   │   OptimizationEngine · GameModeService           │         │
│   │   ActionHistory · BackupManager · RollbackEngine │         │
│   │   RestorePointService                            │         │
│   └────────────────────┬─────────────────────────────┘         │
│                        │                                       │
│                        ▼  (bus + signals)                      │
│   ┌──────────────── ViewModels (MVVM) ───────────────┐         │
│   │ Monitor · Optimize · GameMode · Cleanup         │          │
│   └────────────────────┬─────────────────────────────┘         │
│                        │                                       │
│                        ▼                                       │
│   ┌───── Views (QWidget) ─────┐   ┌───── Theme ─────┐          │
│   │ Dashboard · Optimize      │   │ Palette         │          │
│   │ GameMode  · Monitor       │   │ Typography      │          │
│   │ Cleanup   · Safety        │   │ QSS Stylesheet  │          │
│   │ Settings                  │   │ Custom icons    │          │
│   └───────────────────────────┘   └─────────────────┘          │
└───────────────────────────────────────────────────────────────┘
```

**Why this split?** The `AppController` has no knowledge of Qt widgets. The
views know nothing about psutil, registry keys, or PowerShell. That means
every rule, monitor, or safety feature is independently testable and
swappable.

### Package layout

```
app/
├── core/              # controller, event bus, config, constants, AutoPilot
├── games/             # library scanner + per-game profiles (Steam/Epic/GOG/...)
├── system/            # hardware detection, bottleneck analysis
├── monitoring/        # live performance metrics (+ GPU via win32pdh)
├── optimization/      # rule engine, Game Mode
│   └── rules/         # one file per rule, declarative metadata + apply/restore
├── overlay/           # in-game HUD, FPS tracker, foreground tracker, hotkey
├── cleanup/           # preview-first file cleanup
├── safety/            # action history, backups, rollback, restore points
├── utils/             # logging, paths, formatting, admin check
└── ui/
    ├── theme/         # APEX palette, typography, QSS
    ├── widgets/       # sidebar, toggle, graph, ring gauge, cards,
    │                  #   ticker_bar, hex_panel, brand_mark, fps_panel,
    │                  #   game_tile
    ├── views/         # one file per top-level view (incl. game_hub_view)
    ├── viewmodels/    # thin Qt-signal adapters over the controller
    └── main_window.py
```

---

## Running from source

```powershell
python -m pip install -r requirements.txt
python main.py
```

Python 3.10+ is required. Tested on Windows 10/11 with Python 3.14.

### Useful smoke tests

```powershell
# Offscreen UI — cycles every view to catch render bugs
$env:QT_QPA_PLATFORM="offscreen"; python scripts/smoke_test.py

# End-to-end flows — hardware detection, plan, Game Mode, cleanup scan
python scripts/smoke_flows.py
```

---

## Building a standalone .exe

The project ships with a pre-configured PyInstaller spec:

```powershell
python -m pip install -r requirements.txt
python build_exe.py
```

This produces `dist/GameBoostApex.exe` — a single self-contained executable,
no Python runtime or dependencies required on the target machine.

Under the hood:

1. Collects every `app/` package recursively.
2. Bundles PyQt6 + psutil + WMI.
3. Strips unused Qt plugins for a leaner binary.
4. Embeds an application icon and version metadata.

---

## Safety model

Every optimization rule follows the same contract:

1. **`evaluate()`** — read-only. Decides whether the machine would benefit.
2. **`apply()`** — performs the change and returns a `backup_payload` with
   the prior state.
3. **`restore(payload)`** — reverses the change using that payload.

The `OptimizationEngine` captures each payload through the `BackupManager`
and records an `ActionRecord` in the `ActionHistory`. The Safety tab shows
every action with its status (applied / rolled-back / failed) and exposes
a one-click rollback for any reversible entry.

**Nothing is applied** without:

- An explicit click on **Apply** in the Optimize view,
- A confirmation dialog listing the action count,
- (Optionally) a Windows System Restore point created beforehand.

---

## Extending it

Adding a rule is a single file:

```python
# app/optimization/rules/my_rule.py
class MyRule(OptimizationRule):
    id = "my.rule"
    title = "Something useful"
    category = "power"
    what = "One paragraph on what it does."
    why = "One paragraph on why it helps gaming."
    risk = RISK_LOW
    impact = IMPACT_MODERATE
    reversible = True

    def evaluate(self, hardware):
        return RuleEvaluation(applicable=True, score=40, reason="...")

    def apply(self):
        prev = _read_state()
        _write_new_state()
        return RuleOutcome(ok=True, message="Done", backup_payload={"prev": prev})

    def restore(self, payload):
        _write_state(payload["prev"])
```

Register it in `OptimizationEngine._default_rules()` and it appears in the
plan automatically with its risk/impact badges, evidence line and toggle.

---

## License

Source-available under the MIT license — see `LICENSE`.
