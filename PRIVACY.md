# GameBoostApex — Privacy Policy

**Effective date:** 2026-04-28
**Maintainer:** GameBoostApex project
**Contact:** GitHub Issues on the project's repository

---

## 1. Plain-English summary

GameBoostApex is a Windows desktop optimizer that runs **entirely on your computer**. We do not have a server, we do not maintain accounts, and we do not upload your hardware information, files, settings, or usage history to anyone we control.

The only network calls the app makes are:

- **Network probes you trigger yourself** (DNS Benchmark, Ping Tester) — these contact public DNS resolvers and game-server endpoints directly, never us.
- **Sponsored banner content** — the app fetches a small JSON manifest of currently-running banner creatives from a static URL we host. Click-throughs open the **system browser** at a sponsor page where Microsoft Advertising and/or Google AdSense run; their privacy policies apply on that page.
- **Banner thumbnail images** — pulled directly from the URL listed in the manifest entry (typically a CDN we control).
- **Software-update checks (if enabled in Settings)** — a single HEAD request to GitHub to compare version numbers.

GameBoostApex is ads-supported. You can switch personalized advertising **off** at any time in `Settings → Privacy`, and we serve non-personalized ads in regions where that is legally required (GDPR, UK GDPR, CCPA, LGPD).

---

## 2. What we read from your PC at runtime

To do its job, GameBoostApex reads (but does **not** transmit) standard Windows system information:

| Category          | Examples                                                  | Source                                       |
| ----------------- | --------------------------------------------------------- | -------------------------------------------- |
| Hardware specs    | CPU/GPU model, RAM size, disk model                       | WMI, `psutil`, `Get-PnpDevice`               |
| Live performance  | CPU%, RAM%, GPU%, disk I/O, net I/O                       | Windows performance counters                 |
| Process list      | Running process names, CPU/RAM, network connection counts | `psutil`                                     |
| Driver list       | Installed drivers and their versions                      | WMI `Win32_PnPSignedDriver`                  |
| NVMe SMART data   | Wear %, total bytes written, temperature                  | StorageReliabilityCounter                    |
| PCIe link state   | Link width and speed                                      | Vendor-tools fallback                        |
| Boot timing       | Main path / post-boot durations                           | Windows Event Log (Diagnostics-Performance)  |
| Game launchers    | Steam / Epic / Xbox / GOG / Battle.net / EA installs      | Registry + each launcher's manifest files    |

This is the same data you can see in Task Manager, Device Manager, or PowerShell. We just present it nicely. **None of it is uploaded, ever.**

---

## 3. What we store locally

GameBoostApex writes the following files inside `%LOCALAPPDATA%\GameBoostApexOptimizer\`:

```
config.json          In-app preferences (theme, hotkeys, mode, privacy choices)
history\             Local action log: what you applied, when, was it reversible
stats\               Streak count, achievement progress
reports\             Daily performance reports (FPS averages, plans applied)
benchmarks\          Boot-time history, NVMe SMART snapshots
macros\              Macros you've created in the Tools tab
backups\             Per-action backups used for one-click rollback
ads_manifest.json    Local cache of the current banner-creative rotation
logs\                Rolling diagnostic log (last few sessions)
```

These files **never leave your PC** unless you manually copy them.

---

## 4. What we do NOT collect

- No real name, email, account, login, or password.
- No browsing history, document contents, screenshots, microphone, or camera.
- No keystroke logging.
- No file *contents* (the cleanup module only deletes files inside the categories you tick — it never reads the contents of those files).
- No advertising ID, hardware serial number, MAC address, or IP-based location stored by us.

---

## 5. Network connections

GameBoostApex makes outbound network calls only in these specific situations:

### 5.1 You explicitly trigger them

- **DNS Benchmark** — UDP DNS queries to Cloudflare 1.1.1.1, Google 8.8.8.8, Quad9 9.9.9.9, OpenDNS 208.67.222.222, and your current resolvers, to compare latency. The query asks "what is the IP of `cloudflare.com` / `google.com` / a few common gaming domains?" — no personal data is in the query payload.
- **Game Server Ping** — TCP handshake (port 443) to public matchmaking endpoints listed in the app. Measures connection time only; no payload sent after handshake.

### 5.2 Sponsored banner content (always on while the app is running)

- A `GET` to the URL configured in `ads_manifest_url` (default: a static JSON file we host). The request includes a generic `User-Agent: GameBoostApex/<version>` and **nothing else**. No tracking pixel, no fingerprint, no ad ID.
- A `GET` to each banner's `image_url` to fetch the thumbnail. Same headers.
- When you click a banner, your default browser opens to a UTM-tagged URL — at that point the destination page (which we host) takes over and is governed by section 6.

### 5.3 Software updates *(opt-in, default off)*

A single HEAD request to `https://api.github.com/repos/<owner>/<repo>/releases/latest` to compare the latest tag against your installed version. No identifying headers are sent beyond the standard Python `urllib` user-agent.

### 5.4 What we do NOT do over the network

- No silent "phone home" pings.
- No background telemetry beacons.
- No analytics SDKs (Google Analytics, Mixpanel, Sentry, Amplitude, etc.).
- No CDN-loaded fonts or scripts.
- No embedded web view in the app — the desktop binary itself never executes third-party JavaScript.

---

## 6. Advertising

GameBoostApex is monetized by ads. Two surfaces:

### 6.1 In-app banner

A native Qt banner appears at the bottom of the **Dashboard** and **Game Hub** tabs. The banner shows:

- a small thumbnail (optional),
- a one-line headline + body,
- a "Sponsored" disclosure label,
- a CTA button.

The creative content comes from the JSON manifest described in §5.2. The desktop app itself runs **no third-party ad SDK and no JavaScript**. Clicking the banner opens your default web browser at a UTM-tagged URL — the desktop application is just a traffic source.

### 6.2 Hosted sponsor page (where the actual ad networks run)

The destination URL is a web page we host (typically `https://gameboostapex.app/sponsor`). On that page, **and only on that page**, we run:

| Provider                | What they get                                                  | Their policy                                  |
| ----------------------- | -------------------------------------------------------------- | --------------------------------------------- |
| **Microsoft Advertising** (Audience Network) | IP, user-agent, screen size, page URL, ad cookies | <https://privacy.microsoft.com/privacystatement>          |
| **Google AdSense**      | IP, user-agent, screen size, page URL, ad cookies              | <https://policies.google.com/privacy>         |

This is the legitimate way to use AdSense and Microsoft Advertising for a desktop application: the ads run **inside a real web browser on a real web page**, never embedded inside the app binary. Both networks' Terms of Service explicitly support this pattern.

### 6.3 Cookies and identifiers

The ad providers may set cookies / web-storage entries scoped to **their own domains** (`bat.bing.com`, `googleads.g.doubleclick.net`, etc.) when you visit the sponsor page in your browser. These cookies live in your browser's storage, not next to GameBoostApex's own configuration files. They are not readable by GameBoostApex.

### 6.4 Sponsored insight cards

Inside `Live Insights` you may also see clearly-labelled "**SPONSORED**" partner cards alongside system suggestions. These are static, curated entries from a local list — no network call, no third-party SDK. You can disable them in `Settings → Privacy → Sponsored insight cards`.

### 6.5 Personalized vs non-personalized ads

You can disable ad personalization in `Settings → Privacy → Allow personalized ads`. When personalization is off, the UTM parameters we attach to click-throughs include `npa=1` so the destination page serves non-personalized inventory. Personalization is **off by default** — we only enable it after explicit consent in regions that require it (GDPR, UK GDPR, CCPA, LGPD).

### 6.6 Children

Ads are served as **non-personalized only** if your operating system signals a Limit Ad Tracking preference, or if your account region requires it.

---

## 7. Analytics & telemetry

GameBoostApex ships with telemetry **off by default**. There is currently no telemetry SDK in the application binary.

If a future build adds an opt-in telemetry toggle, it will:

- be clearly labelled in `Settings → Privacy → Share anonymous usage stats`,
- send only aggregate counters (e.g., "rule X applied N times this week", "boot-time histogram bucket"),
- never include hardware identifiers, file paths, process names, or network contents,
- be disclosed in this document **before** it ships, with a one-time in-app notice.

---

## 8. Crash dumps

If GameBoostApex crashes, Windows may write a memory dump to `%LOCALAPPDATA%\CrashDumps\`. We do **not** automatically collect or upload these. If you want to share one to help debug, you can attach it manually to a GitHub issue. The cleanup module includes a "Crash dumps" category so you can wipe them on demand.

---

## 9. Optimizations and your system

GameBoostApex can apply system-level changes (registry tweaks, service start types, scheduled-task disables, power-plan changes). Every one of these:

- runs only when you click **Apply selected**,
- creates a per-rule backup in `backups\` so you can roll it back from `Safety → History`,
- (optionally) creates a Windows System Restore point before applying,
- is documented inside the app: each rule explains *what* it changes and *why*.

We are **not** responsible for system instability caused by changes you choose to apply. The app is provided "as is" without warranty of any kind. Roll-back functionality is best-effort.

---

## 10. Your rights

Because there is no server-side account:

- **Access / export** — every file the app writes is in `%LOCALAPPDATA%\GameBoostApexOptimizer\`. Copy it freely.
- **Deletion** — uninstall the app and delete the folder above. Nothing else needs to happen.
- **Portability** — the JSON / JSONL files in `stats\`, `history\`, and `benchmarks\` are plain text and meant to be moved between PCs.

If you live in a region with a formal data-rights regime (GDPR, UK GDPR, CCPA, LGPD), the same principle applies: there is no server-side data about you for us to export or delete, because there is no server.

For data the **ad providers** receive when you visit the sponsor page in your browser (§6.2), you can opt out via:

- **Microsoft Advertising** — <https://account.microsoft.com/privacy/ad-settings>
- **Google AdSense** — <https://adssettings.google.com/>

---

## 11. Children

GameBoostApex is a system utility intended for adult users. It is not directed at children under 13. We do not knowingly collect data from children. If you believe a child's data has been collected in error, please contact us.

---

## 12. Changes to this policy

If we ever change how the app handles data, we will:

1. Update this document with a new **Effective date**.
2. Show a one-time in-app notice the next time you launch GameBoostApex after the change.
3. Keep the previous version available in the project's Git history.

---

## 13. Contact

Questions? Open an issue on the project's GitHub repository.
