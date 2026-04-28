# Changelog

All notable user-facing changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Insights tab** — auto-troubleshooter wizard, hardware findings (RAM/PCIe/NVMe/Drivers), predictive maintenance forecasts.
- **Stats tab** — daily streak counter, achievement tracker, daily reports, recent boot-time history.
- **Tools tab** — Process Hunter snapshot, DNS benchmark, game-server ping, macro runner.
- Three matching sidebar entries (Insights, Tools, Stats) with new vector icons (spark, wrench, trophy).
- Native, ToS-compliant **AdBanner** widget on Dashboard + Game Hub. Clicks open the system browser at a UTM-tagged sponsor URL.
- Settings → **Privacy & ads** card with sponsored-cards toggle and personalized-ads opt-out (GDPR / CCPA / UK GDPR / LGPD).
- Public `PRIVACY.md` and `docs/MONETIZATION_HOWTO.md` documents.
- Static-site scaffold under `web/` for GitHub Pages: landing, sponsor page (where AdSense + Microsoft Ads run legitimately), banner manifest, privacy page.
- GitHub Actions workflows: release builder, CI smoke test, Pages deploy.

### Fixed
- Optimize tab — apply button no longer drifts away from the card list when the plan is short. Footer is now docked outside the scroll area; empty space below the cards reads as natural padding instead of a hard "gap".
- `OptimizeViewModel.refresh_plan()` no longer crashes after applying a plan (`PlannedAction` has no `hardware`/`current_settings`/`applicable` attributes — was using stale field names).
- `AutoPilot._silent_apply_recommended()` uses `evaluation.applicable` instead of the missing `action.applicable`.
- `ActionCard._refresh_badges()` likewise migrated to `evaluation.applicable`.
- Monitor → FPS panel — values and labels no longer visually overlap when the panel is shorter than the hero column. Replaced the QGridLayout with explicit per-row HBoxes that compute their own min-height from the value font's metrics.
- HudFrame top label ("GB-FPS") was painted at `y = -6` (outside the widget); now drawn at `+4` so it sits inside the panel.
- ActionCard internal margins / spacing tightened so each card feels less loose.

### Changed
- Optimize tab tighter root spacing (18 → 14) and tighter inter-card gap (10 → 8).
- AdBanner no longer requires `QtWebEngine`; renders as native Qt widgets and opens the system browser on click.

## [2.1.0] — 2026-04-15

Initial v2.1 feature wave. See `docs/v2_1_ROADMAP.md` for the full feature list.
