# Security Policy

## Reporting a vulnerability

If you discover a security issue in GameBoost, please **do not** open a
public GitHub issue. Instead:

1. Open a GitHub Security Advisory in this repository
   (`Security` tab → `Report a vulnerability`), **or**
2. Email the maintainer at the address shown on the GitHub profile.

Please include:

- The version of GameBoost (visible in `Settings → About`).
- Your operating system and version (e.g., Windows 11 24H2 x64).
- Whether the app was running as Administrator.
- A reproduction recipe — the smaller, the better.
- The impact you believe the issue has (privilege escalation, data
  leak, system instability, denial-of-service, etc.).

We will acknowledge your report within **72 hours**, agree a remediation
window with you, and credit you in the changelog if you wish.

## Scope

In scope:

- Privilege escalation by unprivileged code shipped inside the app.
- Arbitrary file write / delete outside the documented cleanup
  categories.
- Bypass of the rollback / backup safety stack.
- Network requests to undocumented hosts.
- Embedded credentials / signing keys leaking through the binary.

Out of scope:

- Issues that require an attacker to already have admin rights on the
  machine.
- Issues purely cosmetic (UI glitches, icon misalignment).
- Self-XSS in the local JSON config file.
- Reports against third-party libraries we depend on — please report
  those upstream instead.

## Supported versions

Only the **latest** released version receives security fixes. We do not
backport to older lines.

| Version  | Supported  |
| -------- | ---------- |
| 2.1.x    | ✅ active  |
| < 2.1    | ❌ end-of-life |
