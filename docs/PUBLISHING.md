# GameBoost — Full Publishing Runbook

End-to-end checklist to take this repo from local to **shipped**:
GitHub repo, free GitHub Pages domain, automated release pipeline,
hosted sponsor page (so AdSense + Microsoft Advertising run
legitimately), and Microsoft Store submission.

You only have to do **Phase 0** once. Everything in **Phase 1+** is
either fully automated by GitHub Actions or a one-time toggle.

> **Already baked in**
> All URLs in this repo point at GitHub user **`NikolasGSG`** and repo
> **`pcBoostMax`**. If you ever fork or rename, run the find-replace
> below in your editor of choice — VS Code, Sublime, anything:
>
> | Find                   | Replace                         |
> | ---------------------- | ------------------------------- |
> | `NikolasGSG`               | new GitHub username (if forked) |
> | `pcBoostMax`           | new repo name (if renamed)      |
> | `YOUR_TAG`             | your Amazon Associates tag      |
> | `YOUR_REF`             | your VPN / partner referral id  |
> | `pub-XXXXXXXXXXXXXXXX` | your real AdSense publisher ID  |
>
> Affected files: `app/core/config.py`, `web/**`, `.github/**`,
> `app/monetization/affiliate.py`, `README.md`.

---

## Phase 0 — One-time setup (≈ 30 minutes)

### 0.1 Create the GitHub account + repo

1. Sign up at <https://github.com/signup> if you don't have an
   account yet. **Use a username you're happy living with** — it
   becomes your free domain (`<user>.github.io`).
2. Create a new public repo: <https://github.com/new>
   - **Repository name**: `pcBoostMax` (must match the value baked
     into the URLs in this repo — only change it if you also run
     the `pcBoostMax` find-replace in the table above).
   - **Description**: "Free Windows performance optimizer for gamers".
   - **Visibility**: Public.
   - Do **not** initialize with README / .gitignore / LICENSE —
     this repo already has them.

### 0.2 Initialize git locally + push

From the repo root (`c:\Users\Utilizador\Desktop\pcBoostMax`), in
PowerShell:

```powershell
git init
git add .
git commit -m "chore: initial public commit"
git branch -M main
git remote add origin https://github.com/NikolasGSG/pcBoostMax.git
git push -u origin main
```

If `git` isn't installed: <https://git-scm.com/download/win>.

### 0.3 Enable GitHub Pages

1. Repo → **Settings** → **Pages** (left sidebar).
2. **Source**: pick **GitHub Actions** (not "Deploy from a branch").
3. Save.

That's it. The `.github/workflows/pages.yml` workflow that ships in
this repo will deploy `/web/` automatically on every push to `main`.
After the first push completes, your site is live at:

```
https://NikolasGSG.github.io/pcBoostMax/
```

The desktop app is already pointed at this URL via
`AppConfig.ads_manifest_url`. Once Pages publishes, the in-app banner
starts pulling real creatives.

### 0.4 Tag the first release

This triggers `.github/workflows/release.yml`, which builds the
Windows exe and attaches it to a GitHub Release with a stable
download URL.

```powershell
git tag v2.1.0
git push origin v2.1.0
```

Watch the build in the **Actions** tab. ~3 min later you'll have:

```
https://github.com/NikolasGSG/pcBoostMax/releases/download/v2.1.0/GameBoost-2.1.0-x64.exe
```

That URL is what you paste into Microsoft Partner Center for the
**x64** package field.

### 0.5 Repo cosmetics

Recommended one-time toggles in **Settings**:

- **General → Features** — disable Wiki / Projects if you don't use
  them. Keep Issues + Discussions on.
- **General → Pull Requests** — tick "Automatically delete head
  branches" so merged PR branches clean themselves up.
- **General → Default branch** — `main`.
- **Code security and analysis** — turn on:
  - Dependabot alerts ✅
  - Dependabot security updates ✅
  - Secret scanning ✅
  - Code scanning (CodeQL) — optional but free for public repos.
- **Branches → Branch protection rule** for `main`:
  - Require status checks: pick the `smoke` job from CI.
  - Require pull request reviews: 0 if you're solo, 1 if you have
    collaborators.

---

## Phase 1 — Get into the ad networks (≈ 1–2 weeks elapsed)

> Both networks need to verify the **website**, not the desktop app.
> The site at `NikolasGSG.github.io/pcBoostMax/` is what they
> review. The desktop app is just a traffic source.

### 1.1 Google AdSense

1. Go to <https://www.google.com/adsense/start/>.
2. Add the site URL (your Pages URL).
3. Copy the auto-ads `<script>` snippet into `web/index.html` and
   `web/sponsor/index.html` — both files have a clearly-marked
   `<!-- AdSense ... -->` block ready to receive it.
4. Replace `pub-XXXXXXXXXXXXXXXX` in `web/ads.txt` with your real
   publisher ID.
5. Push to main → Pages redeploys.
6. Click "Request review" in AdSense.
7. Approval takes 1–14 days. Common rejection reasons + fixes:
   - **Insufficient content** — add 3–5 short articles to a `/blog/`
     directory under `web/`.
   - **No privacy policy** — yours is at `/privacy.html`, but make
     sure it's linked from every page.
   - **Site not live** — verify the Pages URL loads in an incognito
     window before requesting review.

### 1.2 Microsoft Advertising

1. <https://about.ads.microsoft.com/> → "I'm a publisher".
2. Add your Pages URL.
3. Paste the UET tag into both HTML files (also marked block).
4. Set up an "audience-network campaign". Approval is similar to
   AdSense, often slightly faster.

### 1.3 Affiliate networks (no waiting)

For day-1 revenue while waiting for AdSense:

| Network                  | URL                                                        |
| ------------------------ | ---------------------------------------------------------- |
| Amazon Associates        | <https://affiliate-program.amazon.com>                     |
| NordVPN                  | <https://nordvpn.com/affiliate/>                           |
| IObit Driver Booster     | <https://www.iobit.com/en/affiliateprogram.php>            |

Replace placeholders in:

- `app/monetization/affiliate.py` — `default_registry()`
- `web/sponsor/index.html` — three `<a class="cta">` URLs
- `web/ads/manifest.json` — three creative `click_url`s

Push, done.

---

## Phase 2 — Microsoft Store submission (optional, ≈ 3 days elapsed)

### 2.1 Sign up for Partner Center

1. <https://partner.microsoft.com/dashboard> → **Sign up as
   developer** ($19 one-time for individuals).
2. Verify your identity.

### 2.2 Reserve the app name

Apps tab → **+ New product** → **App** → reserve `GameBoost` (or a
variant if taken).

### 2.3 Reserve the app identity (one-time)

Microsoft Store rejects EXE/MSI installers under **Policy 10.2.9** (no
installer UI may appear on a no-args launch — UAC is the only allowed
prompt). Even a perfectly silent Inno Setup wrapper can fail their
sandbox validation. The reliable path is **MSIX**, where the Store
itself performs the install. The repo's `release.yml` builds an MSIX
automatically — but only after you wire the three identity values it
needs.

**Look them up once** in Partner Center:

1. Sign in at <https://partner.microsoft.com/dashboard>.
2. **Apps and games** → click **GameBoost** → **Product identity**
   (left sidebar, sometimes shown as "App identity").
3. Copy these three fields verbatim:

| Field shown in Partner Center | Goes into repo variable          |
| ----------------------------- | -------------------------------- |
| **Package/Identity/Name**          | `MSIX_IDENTITY_NAME`             |
| **Package/Identity/Publisher**     | `MSIX_PUBLISHER`                 |
| **Package/Properties/PublisherDisplayName** | `MSIX_PUBLISHER_DISPLAY_NAME` |

Examples (yours will differ):
```
MSIX_IDENTITY_NAME            12345NikolasGSG.GameBoost
MSIX_PUBLISHER                CN=ABCD1234-12AB-34CD-56EF-1234567890AB
MSIX_PUBLISHER_DISPLAY_NAME   NikolasGSG
```

**Wire them into the repo** (one-time):

1. Repo Settings → **Secrets and variables** → **Actions** →
   **Variables** tab → **New repository variable**.
2. Add all three names above with the values from Partner Center.
3. Re-tag the next release. CI will produce
   `GameBoost-X.Y.Z-x64.msix` automatically.

### 2.4 Submit the package URL

In **Packages**:

| Architecture | URL                                                                                                  |
| ------------ | ---------------------------------------------------------------------------------------------------- |
| **x64**      | `https://nikolasgsg.github.io/pcBoostMax/downloads/GameBoost-latest-x64.msix`                        |
| **x86**      | *leave empty*                                                                                        |
| **ARM64**    | *leave empty (or duplicate the x64 URL)*                                                             |

If you have not yet configured the identity variables and you need to
ship _today_, fall back to the Inno Setup installer URL:
`https://nikolasgsg.github.io/pcBoostMax/downloads/GameBoost-latest-Setup.exe`.
Microsoft will probably reject it under Policy 10.2.9, but the binary
itself is silent-by-default so there's a chance it slips through.

### 2.5 Store listing

- **Display name**: GameBoost
- **Short description**: see `README.md` first paragraph.
- **Description**: paste from `README.md`.
- **Category**: Utilities & tools.
- **Age rating**: complete the IARC questionnaire — "all ages, no
  user-generated content".
- **Privacy policy URL**:
  `https://NikolasGSG.github.io/pcBoostMax/privacy.html`
- **Support URL**:
  `https://github.com/NikolasGSG/pcBoostMax/issues`
- **Screenshots**: 4–8 PNGs at 1080p of your favourite tabs. Use the
  Insights, Optimize, Game Hub, and Stats tabs for variety.

### 2.6 Submit and wait

Certification: 24–72 h for first submissions. They mostly check that
the URL works, the binary launches, and the privacy / support URLs
are live.

---

## Phase 3 — Day-to-day workflow

### Add a new optimization rule
1. Edit `app/optimization/rules/...`.
2. Push to main → CI smoke runs.
3. Open a PR if you have collaborators, otherwise merge directly.
4. When you have several improvements, tag a new release:
   ```powershell
   git tag v2.1.1
   git push origin v2.1.1
   ```
5. Update Partner Center with the new release URL.

### Rotate ad creatives
1. Edit `web/ads/manifest.json`.
2. `git commit -am "ads: q3 rotation"` && `git push`.
3. Pages redeploys; desktop app picks up the new manifest within 24 h
   (or immediately on next launch if `ads_manifest.json` cache is
   removed from `%LOCALAPPDATA%\GameBoostOptimizer\`).

### Update the privacy policy
1. Edit `PRIVACY.md`.
2. Mirror the change in `web/privacy.html` summary section.
3. Push. Pages workflow auto-redeploys.

---

## Phase 4 — Optional polish (whenever)

- **Code-signing certificate** — Sectigo / DigiCert OV ($150–$300/yr).
  Eliminates SmartScreen warnings; speeds up Store certification.
  Configure in `build_exe.py` with `--codesign-identity` once you have
  the cert in `.pfx` format.
- **Custom domain** — buy `gameboost.app` (or similar), add it as a
  CNAME in `web/CNAME`, configure DNS at the registrar:
  ```
  Type   Host   Target
  CNAME  www    NikolasGSG.github.io.
  A      @      185.199.108.153
  A      @      185.199.109.153
  A      @      185.199.110.153
  A      @      185.199.111.153
  ```
  Then **Settings → Pages** → custom domain field. Update
  `ads_manifest_url` and `ads_sponsor_url` in `app/core/config.py`,
  push a new tag.
- **Analytics on the sponsor page** — Plausible (privacy-friendly,
  $9/mo) or Cloudflare Web Analytics (free). Don't put GA4 on the
  sponsor page if your privacy policy says you don't ship Google
  Analytics.

---

## Quick reference: what every URL is

| Purpose                          | URL                                                                            |
| -------------------------------- | ------------------------------------------------------------------------------ |
| Project landing page             | `https://NikolasGSG.github.io/pcBoostMax/`                                    |
| Privacy policy (public)          | `https://NikolasGSG.github.io/pcBoostMax/privacy.html`                        |
| Sponsor page (where ads run)     | `https://NikolasGSG.github.io/pcBoostMax/sponsor/`                            |
| Banner manifest (consumed by app)| `https://NikolasGSG.github.io/pcBoostMax/ads/manifest.json`                   |
| Latest x64 download              | `https://github.com/NikolasGSG/pcBoostMax/releases/latest/download/GameBoost-2.1.0-x64.exe` |
| Issue tracker                    | `https://github.com/NikolasGSG/pcBoostMax/issues`                             |
| Source                           | `https://github.com/NikolasGSG/pcBoostMax`                                    |

That's everything. Push the repo and the rest is mostly clicks.
