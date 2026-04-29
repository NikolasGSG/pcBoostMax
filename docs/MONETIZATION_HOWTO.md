# GameBoostApex — Monetization Setup Runbook

This is the full, step-by-step guide to turning GameBoostApex from a free
optimizer into a revenue-generating product **legitimately**, using
Google AdSense + Microsoft Advertising, **without violating either
network's Terms of Service**.

The architecture you've already shipped does not embed any third-party
ad SDK in the desktop binary. Instead:

1. The app shows native Qt banners pulled from a JSON manifest you
   control.
2. Click-throughs open the user's default browser.
3. The destination page (which you host) is a normal web page where
   AdSense and Microsoft Advertising tags are 100 % allowed.

Result: you get real CPM/CPC revenue, the user sees only one click-out
per ad they actually want to learn more about, and neither ad network
has any complaint about your distribution model.

---

## Part 1 — One-time hosting setup

### 1.1 Buy or pick a domain

Anything works. The defaults in `app/core/config.py` use
`https://gameboostapex.app/` — change `ads_manifest_url` and
`ads_sponsor_url` to whatever domain you own. If you don't have one,
GitHub Pages on a free `<user>.github.io` subdomain works fine for
both AdSense and Microsoft Advertising approvals.

### 1.2 Stand up a static site

Easiest path: a public GitHub repo named `<user>.github.io` (or any
repo with Pages enabled). Recommended layout:

```
your-site-repo/
├── index.html               ← project landing page
├── sponsor/
│   └── index.html           ← the page the desktop app opens
├── ads/
│   ├── manifest.json        ← the JSON the app fetches
│   └── img/
│       ├── nvme-q2.png
│       └── ram-q2.png
└── privacy.html             ← public-facing copy of PRIVACY.md
```

Push it; Pages serves it instantly at
`https://<user>.github.io/sponsor/` etc. You can later swap to a
custom domain in Pages → Settings.

### 1.3 First version of `manifest.json`

Drop this into `ads/manifest.json` on your site:

```json
{
  "version": 1,
  "fetched_at": "2026-04-28T11:00:00Z",
  "creatives": [
    {
      "id": "house-launch-2026q2",
      "headline": "Boost game load times — pick the right NVMe",
      "body": "Curated picks under $80 from the 990 Pro down to the SN770.",
      "cta": "See picks",
      "click_url": "https://<your-site>/sponsor/?slot=nvme",
      "image_url": "https://<your-site>/ads/img/nvme-q2.png",
      "sponsor": "GameBoostApex Picks",
      "weight": 1.0,
      "expires_at": "2026-12-31T23:59:59Z"
    }
  ]
}
```

That's enough for the app to start showing a real banner immediately.
Add more entries to rotate. The widget already does weighted random
selection.

---

## Part 2 — Get into the ad networks

### 2.1 Google AdSense approval

Important: AdSense applies to **the website**, not to the desktop app.
The app is just a referral source.

1. Sign up at <https://www.google.com/adsense/start/> with your
   Pages-hosted domain.
2. Add the auto-ads `<script>` block to `<head>` of every page on your
   static site (Google copy-pastes it from the AdSense dashboard
   during sign-up).
3. Add an `ads.txt` file at the **site root** (next to `index.html`):
   ```
   google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0
   ```
   Replace `pub-XXXXXXXXXXXXXXXX` with your real publisher ID.
4. Wait for review (usually 1–14 days). They mostly check:
   - Do you have a privacy policy? **Yes — your `privacy.html` is the
     public copy of `PRIVACY.md`.**
   - Real, non-spammy content? Add a few useful articles to the
     landing page (e.g. "How to upgrade NVMe storage in 5 minutes").
   - No prohibited content. Optimizer + gaming hardware is well
     within their guidelines.
5. Once approved, AdSense auto-injects ad slots. You don't need to
   change anything in the desktop app.

### 2.2 Microsoft Advertising / Audience Network approval

Microsoft Advertising for publishers is on the same kind of approval
flow:

1. Sign up at <https://about.ads.microsoft.com/> as a publisher.
2. Paste the `mscore.js` snippet they hand you into `<head>` of your
   pages.
3. Optional but recommended: add an `app-ads.txt` if you also intend
   to do mobile (not required for desktop traffic).
4. Wait for review. Same content / privacy policy bar as AdSense.

You can run **both networks at the same time** — most ad managers
(EZoic, Mediavine, Snigel) auto-rotate AdSense + Microsoft to maximize
CPM. The desktop app doesn't care which provider serves any given
impression.

### 2.3 Affiliate networks (instant approvals — no waiting)

For day-one revenue while AdSense is in review:

| Network                  | Sign-up URL                                         | Typical payout       |
| ------------------------ | --------------------------------------------------- | -------------------- |
| Amazon Associates        | <https://affiliate-program.amazon.com>              | 1 – 4 % AOV          |
| Newegg Affiliate         | <https://www.newegg.com/promotions/affiliate-program> | 0.5 – 4 % AOV        |
| NordVPN Affiliate        | <https://nordvpn.com/affiliate/>                    | $40 – 80 / signup    |
| Cloudflare WARP          | brand sponsorship                                   | flat fee             |
| IObit Driver Booster     | <https://www.iobit.com/en/affiliateprogram.php>     | $2 – 5 / install     |

These slot directly into `app/monetization/affiliate.py` —
`default_registry()` already has placeholders. Just swap the
`YOUR_REF` / `YOUR_TAG` strings for your real IDs.

---

## Part 3 — Hooking the desktop app to your real URLs

Two strings in `app/core/config.py`:

```python
ads_manifest_url: str = "https://gameboostapex.app/ads/manifest.json"
ads_sponsor_url:  str = "https://gameboostapex.app/sponsor"
```

Either:

- **edit them directly and rebuild** (quickest), or
- override per-user-installation by editing the user's
  `%LOCALAPPDATA%\GameBoostApexOptimizer\config.json` after the first
  launch (handy for white-label builds without rebuilding).

The values are read on every banner refresh, so a config change takes
effect on the next refresh — no restart required.

---

## Part 4 — Day-to-day rotation

Adding or rotating creatives is just a `git push` to your Pages repo
that updates `ads/manifest.json`. Within 24 h every running app picks
up the change automatically (the on-disk cache TTL is one day; manual
refresh by deleting `%LOCALAPPDATA%\GameBoostApexOptimizer\ads_manifest.json`).

Recommended editorial cadence:

- **Weekly** — refresh creatives, rotate seasonal partners.
- **Monthly** — review CTR per `creative.id` (you'll see it in your
  destination page's analytics — that's what the UTM tags are for).
- **Quarterly** — kill creatives below 0.5 % CTR, double-down on the
  top 20 %.

---

## Part 5 — What you should *never* do

To keep both ad networks happy long-term:

- ❌ **Don't embed a `QWebEngineView` inside the app and load AdSense
  there.** That's the textbook ToS violation.
- ❌ **Don't auto-click your own banners.** AdSense bans accounts for
  click fraud at the second offence.
- ❌ **Don't hide the "Sponsored" disclosure.** Both networks require
  it; the widget shows it by default.
- ❌ **Don't bundle the sponsor page into the installer**. The page
  must live on the open web and be reachable in any browser.
- ❌ **Don't run the auto-ads script *and* manual ad units on the
  same impression** — AdSense considers that ad stuffing.

Keep to the model in this document and you're operating exactly the
way the networks expect of a "publisher with a desktop traffic
source", which is a fully supported category.

---

## Part 6 — Revenue back-of-envelope

Rough numbers for a small optimizer (these are conservative):

| Stage                                 | Daily impressions | Net revenue / month |
| ------------------------------------- | ----------------- | ------------------- |
| 5 000 DAU, 1 banner-load / session    | 5 000             | $30 – $80           |
| + 5 % click-through to sponsor page   | 250 page views    | $5 – $30 AdSense    |
| + 1 affiliate signup / 100 page views | 75 / month        | $20 – $400          |
| **Total**                             |                   | **~$55 – $510 / mo** |

Scaling to 50 k DAU multiplies everything by ~10. The variance
above comes mostly from affiliate vertical (VPN > hardware > info
products).

---

## Part 7 — Compliance checklist before you ship publicly

- [ ] `PRIVACY.md` linked from your hosted `privacy.html`
- [ ] Settings → Privacy → "Allow personalized ads" toggle visible
- [ ] Settings → Privacy → "Sponsored insight cards" toggle visible
- [ ] AdSense account approved
- [ ] Microsoft Advertising account approved (optional, can ship without)
- [ ] `ads.txt` deployed with your real publisher ID
- [ ] Affiliate IDs swapped into `default_registry()` (no `YOUR_TAG`)
- [ ] Sponsor page renders correctly on mobile (incoming link from
  desktop banners frequently opens on the user's phone)
- [ ] Sponsor page passes Google's [Mobile-Friendly Test](https://search.google.com/test/mobile-friendly)
- [ ] One-line GDPR cookie banner on the sponsor page (any open-source
  banner library works — try Klaro or Cookieconsent)

That's it. Once these are checked, you're live.
