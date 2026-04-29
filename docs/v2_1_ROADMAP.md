# GameBoostApex v2.1 — Feature Roadmap (Ads-Only, Free Forever)

> **Monetization model:** banner ads + sponsored insight cards.
> **The full app stays free.** No paywalls, no rewarded-ad gates, no
> "watch this ad to unlock the scan" friction.

The ads-only model rewards **engagement** — every minute the user spends
in the app is an ad impression. So features are picked for one of three
goals:

- **D — Daily-use hooks** (memory trim, daily report, achievements, tray actions) → return visits = ad views
- **S — Stickiness** (per-game profiles, dashboards, history) → longer sessions
- **V — Virality / acquisition** (share cards, leaderboards) → free users coming in the door

Each feature lists `Effort` (S=1-2 days, M=3-5 days, L=1-2 weeks),
`Why now`, and the goal letter.

---

## Group A — Performance & FPS Boosters *(core differentiators)*

### A1. Memory Trim / Standby List Purger  &nbsp;`Effort: S` `Goal: D`
- **What:** clears Windows Standby cache and trims working sets of
  background processes — frees 1-4 GB of RAM in one click. Hugely visible
  in the FPS panel right after.
- **Why now:** instant gratification → daily-use feature → daily ad views.
- **Hook:** call `SetSystemFileCacheSize` + `EmptyWorkingSet` on each
  non-game PID. Wrap in a `MemoryService` like the existing services.

### A2. Service Tweaker  &nbsp;`Effort: M` `Goal: S`
- **What:** disables bloat Windows services (DiagTrack, Connected User
  Experiences, Xbox Game DVR if disabled, Print Spooler when no printer
  detected, etc.). Each service has a per-rule `why` and revert path.
- **Why now:** every Reddit/YouTube optimization guide covers this; we
  can be the safe one-click version.
- **Hook:** new ruleset under `app/optimization/rules/services/`.

### A3. Background App Tamer  &nbsp;`Effort: M` `Goal: S`
- **What:** when a fullscreen game is detected, suspend processes on a
  user-managed list (Discord, Slack, Spotify, Chrome). Auto-resume on
  game exit.
- **Why now:** passive, "set and forget" value while the user games —
  builds trust without needing them to open the app.
- **Hook:** extend `GameDetector` callbacks to `ProcessSuspender` (we
  already have the suspend primitive in `GameProfileService`).

### A4. Process Hunter  &nbsp;`Effort: S` `Goal: S`
- **What:** sortable process tree (CPU%, RAM, network), one-click kill,
  flags suspicious processes (high CPU + unsigned binary). Our version of
  Task Manager but prettier.
- **Why now:** power users open this **constantly** during sessions.
- **Hook:** new `ProcessHunterView` using `psutil` and a `QTreeView`.

### A5. Press-to-Boost Hotkey  &nbsp;`Effort: S` `Goal: D`
- **What:** a single global hotkey (default `Ctrl+Shift+B`) triggers a
  30-minute "boost burst": Game Mode + memory trim + service kill + power
  plan switch. Auto-reverts after 30 min.
- **Why now:** marketable in one screenshot ("press one button — boost
  for 30 minutes"). Viral on TikTok/YouTube Shorts.
- **Hook:** reuse `GlobalHotkey` infrastructure, wire to a new
  `BoostBurstService`.

---

## Group B — Game-Specific Power Tools

### B1. Per-Game Custom Profiles UI  &nbsp;`Effort: M` `Goal: S`
- **What:** the data model already exists (`GameProfileService`). Add a
  proper editor view: priority, affinity, suspended-process list, custom
  launch arguments, INI tweaks for known engines (Unreal, Source).
- **Why now:** profiles are why power users **come back**. The data
  layer is done; we just need the UI.

### B2. One-Click Game Folder Mover  &nbsp;`Effort: L` `Goal: V`
- **What:** drag a Steam/Epic game from HDD → SSD. Uses `robocopy` with
  resume support, then re-points launcher manifests at the new path.
  Verifies hash post-copy.
- **Why now:** huge pain point. People share screenshots when this works.
- **Hook:** new `GameMover` service. Steam supports this natively but
  we'd add Epic/GOG/Battle.net which don't.

### B3. Shader Cache Manager  &nbsp;`Effort: M` `Goal: S`
- **What:** locates per-game DirectX/Vulkan shader caches (DXVK, NVIDIA,
  AMD), shows total size, lets the user pre-warm before a session or
  clear after a driver update.
- **Why now:** shader-comp stutter is the #1 PC-gaming complaint.
- **Hook:** known-paths registry under `%LOCALAPPDATA%`, `D3DSCache`,
  vendor caches under `%PROGRAMDATA%\NVIDIA Corporation\NV_Cache`.

### B4. Game File Verifier  &nbsp;`Effort: S` `Goal: S`
- **What:** trigger Steam's `verify_integrity` from inside our app, plus
  manual SHA-1 verification for non-Steam launchers using their manifests.
- **Hook:** call `steam://validate/<appid>` URI for Steam; manifest
  parsing for the rest.

---

## Group C — Hardware & Driver Tools

### C1. Driver Auditor  &nbsp;`Effort: M` `Goal: D` *(highest sponsored-card value)*
- **What:** scans GPU/chipset/network/audio drivers, reports versions,
  links to vendor download pages. Sponsored card slot for "auto-update
  with Driver Booster" partner.
- **Hook:** `Win32_PnPSignedDriver` WMI query + bundled
  `data/driver_index.json` with latest known versions per device.

### C2. RAM Speed / XMP Checker  &nbsp;`Effort: S` `Goal: V`
- **What:** detects if RAM is running below its rated XMP/EXPO speed
  (super common — 80% of users with kit-marketed-as-3600 are on 2133).
  Shows a "your RAM is running 41% slower than rated" card with a
  one-pager link explaining how to enable XMP in BIOS.
- **Hook:** `wmic memorychip get` for current speed, parse SPD via
  `Get-CimInstance Win32_PhysicalMemory` for max rated speed.

### C3. PCIe Link Verifier  &nbsp;`Effort: S` `Goal: V`
- **What:** confirms GPU is on full x16 PCIe link at correct generation.
  Common laptop/eGPU/dual-GPU issue. "Your GPU is at PCIe x8 Gen3 but
  supports x16 Gen4 — check your motherboard layout."
- **Hook:** `nvidia-smi -q` for NVIDIA, `rocm-smi` for AMD, fallback to
  parsing DXGI adapter description.

### C4. NVMe / SSD Health Watch  &nbsp;`Effort: M` `Goal: D`
- **What:** SMART data — temperature, percent-used (wear), TBW, host reads/
  writes, uncorrectable errors. Daily check; alerts at 80%/90% wear.
  Sponsored card slot for replacement-SSD partners.
- **Hook:** `smartctl` (bundled) or PowerShell `Get-PhysicalDisk` +
  `Get-StorageReliabilityCounter`.

### C5. CPU/GPU Undervolt Helper  &nbsp;`Effort: M` `Goal: S`
- **What:** **does not undervolt automatically** — too dangerous. Instead
  detects if Intel XTU / AMD Curve Optimizer / MSI Afterburner is
  installed, surfaces the right tool, links to a step-by-step guide.
- **Why ads-friendly:** sponsored card for AIDA64 / HWiNFO Pro / OCCT.

---

## Group D — Network & Latency

### D1. Network Optimizer  &nbsp;`Effort: M` `Goal: S`
- **What:** disable Nagle's algorithm, set `TcpAckFrequency=1`, enable
  `NetworkThrottlingIndex` off, set RWIN. Reversible from Safety log.
  All optional, every change has a "why" tooltip.
- **Hook:** new ruleset in `app/optimization/rules/network/`.

### D2. DNS Benchmark + One-Click Switch  &nbsp;`Effort: S` `Goal: D`
- **What:** ping the user's current DNS + Cloudflare (1.1.1.1) + Google
  (8.8.8.8) + Quad9 (9.9.9.9) + AdGuard. Show ranked list with avg/jitter.
  One-click apply on active interface.
- **Hook:** `socket.gethostbyname_ex` + manual UDP DNS queries with
  perf timing.

### D3. Bandwidth Monitor by App  &nbsp;`Effort: M` `Goal: S`
- **What:** live tree of which app is using your upload/download. Like
  `nethogs` for Windows.
- **Hook:** ETW (Event Tracing for Windows) or PowerShell
  `Get-NetTCPConnection` + `psutil.net_io_counters(pernic=True)`.

### D4. Game Server Ping Tester  &nbsp;`Effort: S` `Goal: V`
- **What:** pings major game-server endpoints (CS2, Valorant, LoL,
  Fortnite, Apex) for the user's region. Shows a colour-coded grid; lets
  you screenshot a "best regions for me" card. Highly shareable.
- **Hook:** bundled `data/game_servers.json` with public endpoints.

---

## Group E — Monitoring & Insights *(deeper Live Insights)*

### E1. Stutter Detector  &nbsp;`Effort: M` `Goal: S`
- **What:** analyses frametime variance from `FpsTracker.history()`,
  flags microstutter events, correlates with disk activity / network
  spikes / thermal throttling. Surfaces "your stutters at 17:42 line up
  with disk activity from `OneDrive.exe`".
- **Hook:** new `StutterAnalyzer` consuming `MonitorSampler` + `FpsTracker`.

### E2. Boot Time Benchmark  &nbsp;`Effort: S` `Goal: D`
- **What:** measures time-to-desktop after each restart, tracks history.
  Shows "+12% faster than 30 days ago" deltas. Highly engaging stat.
- **Hook:** Windows Event Log `Microsoft-Windows-Diagnostics-Performance`
  has boot-time entries (event id 100).

### E3. Daily Performance Report  &nbsp;`Effort: S` `Goal: D` *(prime ad slot)*
- **What:** every 24 h, generate a one-page card on the Dashboard:
  "Yesterday: 4 h gaming, 187 FPS avg, 0 critical stutters, 1 cleanup
  saved 2.3 GB". Persistent below the hero.
- **Why ads-friendly:** users open the app daily to see this → daily
  banner impression.
- **Hook:** persist daily aggregates to `daily_reports.json`, build a
  `DailyReportCard` widget.

### E4. Anomaly Alerts  &nbsp;`Effort: M` `Goal: D`
- **What:** establishes baselines (idle CPU temp, idle RAM use, idle disk
  I/O) over a rolling 7-day window. Tray notifications when something is
  >2σ above baseline.
- **Hook:** extend `LiveInsightEngine` with z-score detection.

### E5. Game Benchmark Mode  &nbsp;`Effort: L` `Goal: V`
- **What:** during a user-defined window, captures FPS/frametime/CPU%/GPU%/
  temps. Saves to `benchmarks/` as JSON. Side-by-side **Before vs After
  tuning** view + PNG export with a "Optimised by GameBoostApex" watermark.
- **Why ads-friendly:** the watermarked share card spreads on Discord/
  Reddit → free user acquisition.

---

## Group F — Engagement & Stickiness *(ads-only model needs these)*

### F1. Streaks & Achievements  &nbsp;`Effort: S` `Goal: D`
- **What:** unlock badges for "10 days in a row", "100 hours of Game Mode",
  "Cleaned 50 GB total", "Applied first plan". Shown on a new "Stats"
  page off the sidebar.
- **Why ads-friendly:** classic engagement loop — return visits compound.

### F2. Share Card Generator  &nbsp;`Effort: S` `Goal: V`
- **What:** export a 1200×630 PNG for Twitter/Reddit/Discord: "+28 FPS in
  CS2 with GameBoostApex — gameboostapex.app". Triggered after benchmark runs and
  major plan applications.
- **Hook:** new `ShareCardRenderer` using `QPainter` to compose the PNG.

### F3. Quick Actions on Tray  &nbsp;`Effort: S` `Goal: D`
- **What:** right-click the tray icon → instant "Memory Trim", "Game
  Mode", "Cleanup". No window open required. Each click = a session.
- **Hook:** extend `GameBoostApexTray` with new menu entries.

### F4. Customisable Dashboard  &nbsp;`Effort: M` `Goal: S`
- **What:** drag-to-reorder tiles; hide/show specific cards (FPS, CPU,
  RAM, Game Mode, Daily Report). Saved per user.
- **Hook:** new `DashboardLayoutConfig` and `QDrag`-based reordering.

### F5. Themes & Custom HUD Layouts  &nbsp;`Effort: S` `Goal: V`
- **What:** alternate palettes (Cyber Pink, Stealth Mono, Synthwave),
  custom HUD widgets (clock, weather, Discord status). Free for all —
  cosmetics drive social shares.
- **Hook:** `Theme.from_preset(name)` exists; just add presets and a picker.

---

## Group G — Smart / AI-style *(lightweight, no ML)*

### G1. AI Game Profile Generator  &nbsp;`Effort: M` `Goal: V`
- **What:** detects the user's hardware tier + the game, produces a
  recommended profile via a hand-written rule engine. Marketed as "AI
  Auto-Tuner" — works offline, no model needed.
- **Hook:** new `ProfileGenerator` with rules like *if RAM ≥ 32 GB → set
  large-pages*, *if CPU has e-cores → set affinity to p-cores only*.

### G2. Auto-Troubleshooter Wizard  &nbsp;`Effort: M` `Goal: D`
- **What:** "I'm having a problem" → pick symptom (stutter / FPS drop /
  crash on launch / network lag) → runs targeted diagnostics → suggests
  the right ruleset. Onboarding for non-experts.
- **Hook:** new `TroubleshooterFlow` with decision trees mapping symptoms
  to rules.

### G3. Predictive Maintenance  &nbsp;`Effort: S` `Goal: D`
- **What:** "Your SSD wear is 70% — at current write rate, expect failure
  in ~6 months." Sponsored-card slot for replacement SSDs.
- **Hook:** linear regression on SMART `Percentage_Used` over the daily
  report history.

---

## Group H — Power-User / Quality of Life

### H1. CLI Mode  &nbsp;`Effort: S` `Goal: S`
- **What:** `gameboostapex.exe game-mode --on`, `gameboostapex.exe cleanup --run`,
  `gameboostapex.exe profile apply --game CS2`. Streamers love this.
- **Hook:** thin `argparse` wrapper that talks to a running instance via
  named pipe, falls back to spinning one up headless.

### H2. Plugin System  &nbsp;`Effort: M` `Goal: V`
- **What:** drop-in third-party rules under `%LOCALAPPDATA%/GameBoostApex/
  rules/external/`. Each plugin is a signed Python file declaring an
  `OptimizationRule` subclass. Community can publish on GitHub.
- **Hook:** `PluginLoader` that scans the dir on startup, sandboxes
  imports.

### H3. Macro Recorder  &nbsp;`Effort: M` `Goal: S`
- **What:** record a sequence of optimization actions as a macro, replay
  later or share as JSON.
- **Hook:** `ActionHistory` already records; add an `export_as_macro`
  method and a "Run macro" button.

---

## Suggested 90-day shipping order (ads-only flavour)

| Week | Milestone |
|------|-----------|
| 1 | **Memory Trim (A1)** + **Press-to-Boost (A5)** — both small, both viral |
| 2 | **Daily Performance Report (E3)** — primary new ad slot |
| 3 | **Streaks & Achievements (F1)** + **Share Card Generator (F2)** |
| 4 | **Quick Actions on Tray (F3)** + **Boot Time Benchmark (E2)** |
| 5 | **Driver Auditor (C1)** + sponsored-card infrastructure |
| 6 | **Network Optimizer (D1)** + **DNS Benchmark (D2)** |
| 7 | **Service Tweaker (A2)** + **Background App Tamer (A3)** |
| 8 | **Game Benchmark Mode (E5)** + share-card hooks |
| 9 | **Per-Game Profile Editor UI (B1)** |
| 10 | **NVMe Health (C4)** + **Stutter Detector (E1)** |
| 11 | **Auto-Troubleshooter Wizard (G2)** + **AI Profile Generator (G1)** |
| 12 | **Microsoft Store packaging (MSIX)** + public launch |

---

## Ads-only monetization plan (the rules)

### Ad placements *(what ships)*
1. **Banner ad** — bottom of Dashboard + Game Hub. 728×90, lazy-loaded
   `QWebEngineView`. **Never** on Optimize / Safety / Settings.
2. **Sponsored insight cards** — occasional clearly-marked "Sponsored"
   card mixed into Live Insights. Pay-per-conversion.
3. **Sponsored hardware-health card** — when SSD wear / GPU temp triggers
   a bottleneck, surface a "Recommended replacement" card. Always native.
4. **First-run consent dialog** — required for GDPR / CCPA. One screen:
   *"Show ads?" (Yes — keeps the app free / No — exit)* and a separate
   *"Personalised ads?" (Yes / No)* checkbox.

### What we deliberately **don't** ship
- ❌ Interstitial ads (full-screen between actions) — kills UX.
- ❌ Rewarded ads ("watch a 30 s ad to unlock") — breaks the "free" promise.
- ❌ Toast/notification ads — annoying, fails Microsoft Store review.
- ❌ Email harvesting — we're not a SaaS.

### Ad providers (Windows desktop apps)
| Provider | Why | Apply at |
|----------|-----|----------|
| **Microsoft Advertising** | Made for Win desktop apps, integrates w/ Microsoft Store | https://about.ads.microsoft.com |
| **Google AdSense for Apps** | Highest fill rates globally, works in WebView | https://adsense.google.com |
| **Adsterra / PropellerAds** | Gaming-niche networks, easier approval | each network's portal |
| **Direct sponsorships** | Cut out the network for high-CPM partners (NordVPN, Razer, MSI) | direct outreach |

Recommended: ship with **Microsoft Advertising primary, AdSense secondary**.
Direct sponsorships unlock once you hit ~5 k DAU.

### Revenue projections *(rough)*
At **5 k DAU**, ~3 sessions/user/day, 2 banner views/session = 30 k daily
impressions. At a $0.50 CPM (conservative for utility apps): **~$450/month**.
Sponsored cards stack on top — one good partner deal can match the
entire banner revenue.

### Telemetry (opt-in, for ad business KPIs)
- Daily active users
- Sessions per DAU + session length
- Banner impressions + CTR
- Sponsored-card impressions + clicks + conversions
- Crash-free rate

### Distribution
- **Microsoft Store** — primary. Free signing first year. Submit MSIX.
- **Direct download** from a landing page — secondary; portable .exe with
  in-app updater.
- **itch.io** — tertiary, for SEO / discoverability.

---

## Done as of v2.0

- All UI bugs fixed (Monitor brush leak, Optimize empty space, Settings toggles)
- Startup: 4295 ms → 1283 ms (70% faster)
- Lazy view loading + async hardware detection
- Per-game profile data model + Game Hub view
- AutoPilot service for hands-free optimization
- 9-view smoke + flow + settings test suites
- v2.0 .exe shipped (40 MB, single-file)
