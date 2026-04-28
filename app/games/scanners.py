"""Launcher scanners — Steam / Epic / GOG / Battle.net / Xbox / Riot.

Each scanner is a small standalone function ``scan_<launcher>() -> Iterable[Game]``
that knows where the launcher records its installed apps on Windows and
reads the manifest formats. They never touch the network — strictly local
disk + registry — so they're safe to run on app startup.

If a launcher isn't installed, the matching scanner just yields nothing
and silently logs a debug line.

The :func:`scan_all` aggregator runs every scanner with ``contextlib.suppress``
so a single bad install can never block the rest.
"""
from __future__ import annotations

import contextlib
import os
import re
import winreg
from pathlib import Path
from typing import Iterable, Iterator, List

from ..utils.logger import get_logger
from .library import Game, Launcher

log = get_logger("games.scanners")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_registry(hive: int, path: str, name: str = "") -> str:
    try:
        with winreg.OpenKey(hive, path) as k:
            v, _ = winreg.QueryValueEx(k, name)
            return str(v)
    except FileNotFoundError:
        return ""
    except OSError:
        return ""


def _enum_subkeys(hive: int, path: str) -> List[str]:
    out: list[str] = []
    try:
        with winreg.OpenKey(hive, path) as k:
            i = 0
            while True:
                try:
                    out.append(winreg.EnumKey(k, i))
                except OSError:
                    break
                i += 1
    except OSError:
        pass
    return out


def _safe_id(launcher: Launcher, native_id: str) -> str:
    sid = re.sub(r"[^a-zA-Z0-9._-]", "_", native_id or "")
    return f"{launcher.value}:{sid}" if sid else f"{launcher.value}:{abs(hash(native_id)) % 10**9}"


def _largest_exe(folder: Path) -> str:
    """Best-guess primary executable: largest .exe in the install folder."""
    try:
        candidates = [p for p in folder.glob("**/*.exe")
                      if "redist" not in str(p).lower()
                      and "vc_" not in p.name.lower()
                      and "crash" not in p.name.lower()
                      and "unin" not in p.name.lower()]
        if not candidates:
            return ""
        candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
        return str(candidates[0])
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Steam
# ---------------------------------------------------------------------------

_STEAM_VDF_RE = re.compile(r'"(\w+)"\s+"([^"]*)"')


def _parse_acf(path: Path) -> dict:
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return out
    for k, v in _STEAM_VDF_RE.findall(text):
        out[k] = v
    return out


def _steam_library_paths(steam_root: Path) -> list[Path]:
    """Return list of Steam library folders, including default + extra ones."""
    libs = [steam_root / "steamapps"]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        try:
            text = vdf.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r'"path"\s+"([^"]+)"', text):
                p = Path(m.group(1).replace("\\\\", "\\")) / "steamapps"
                if p.exists() and p not in libs:
                    libs.append(p)
        except Exception:
            log.exception("Steam libraryfolders.vdf parse failed")
    return libs


_STEAM_NOISE_NAMES = {
    "steamworks common redistributables",
    "steam linux runtime",
    "steam linux runtime - soldier",
    "steam linux runtime - sniper",
    "steam audio",
    "proton experimental",
}
_STEAM_NOISE_KEYWORDS = ("proton ", "steam linux runtime", "redistributables")


def scan_steam() -> Iterator[Game]:
    steam_path = _read_registry(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath")
    if not steam_path:
        steam_path = _read_registry(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")
    if not steam_path:
        return
    root = Path(steam_path)
    if not root.exists():
        return
    log.info("Steam detected at %s", root)
    for lib in _steam_library_paths(root):
        for acf in lib.glob("appmanifest_*.acf"):
            data = _parse_acf(acf)
            appid = data.get("appid", "")
            name = data.get("name", "").strip()
            install = data.get("installdir", "").strip()
            if not (appid and name):
                continue
            n_lower = name.lower()
            if n_lower in _STEAM_NOISE_NAMES:
                continue
            if any(kw in n_lower for kw in _STEAM_NOISE_KEYWORDS):
                continue
            install_dir = (lib / "common" / install) if install else lib / "common"
            yield Game(
                id=_safe_id(Launcher.STEAM, appid),
                name=name,
                launcher=Launcher.STEAM,
                install_dir=str(install_dir) if install_dir.exists() else "",
                appid=appid,
                launch_uri=f"steam://rungameid/{appid}",
                exe_path=_largest_exe(install_dir) if install_dir.exists() else "",
                size_bytes=int(data.get("SizeOnDisk") or 0),
                last_played=float(data.get("LastPlayed") or 0),
            )


# ---------------------------------------------------------------------------
# Epic Games
# ---------------------------------------------------------------------------

def scan_epic() -> Iterator[Game]:
    program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
    manifest_dir = Path(program_data) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    if not manifest_dir.exists():
        return
    log.info("Epic Games detected, manifests at %s", manifest_dir)
    import json
    for item in manifest_dir.glob("*.item"):
        try:
            data = json.loads(item.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        name = data.get("DisplayName", "").strip()
        if not name:
            continue
        app_name = data.get("AppName", "")
        catalog_id = data.get("CatalogItemId", "")
        install_loc = data.get("InstallLocation", "")
        launch_exe = data.get("LaunchExecutable", "")
        exe = (Path(install_loc) / launch_exe) if (install_loc and launch_exe) else None
        yield Game(
            id=_safe_id(Launcher.EPIC, app_name or catalog_id or name),
            name=name,
            launcher=Launcher.EPIC,
            install_dir=install_loc,
            exe_path=str(exe) if exe and exe.exists() else "",
            appid=app_name,
            launch_uri=f"com.epicgames.launcher://apps/{app_name}?action=launch&silent=true",
        )


# ---------------------------------------------------------------------------
# GOG Galaxy
# ---------------------------------------------------------------------------

def scan_gog() -> Iterator[Game]:
    base = r"SOFTWARE\WOW6432Node\GOG.com\Games"
    for sub in _enum_subkeys(winreg.HKEY_LOCAL_MACHINE, base):
        path = base + "\\" + sub
        name = _read_registry(winreg.HKEY_LOCAL_MACHINE, path, "GAMENAME") \
            or _read_registry(winreg.HKEY_LOCAL_MACHINE, path, "gameName")
        install = _read_registry(winreg.HKEY_LOCAL_MACHINE, path, "PATH") \
            or _read_registry(winreg.HKEY_LOCAL_MACHINE, path, "path")
        exe = _read_registry(winreg.HKEY_LOCAL_MACHINE, path, "EXE")
        gameid = sub
        if not (name and install):
            continue
        yield Game(
            id=_safe_id(Launcher.GOG, gameid),
            name=name,
            launcher=Launcher.GOG,
            install_dir=install,
            exe_path=str(Path(install) / exe) if exe else _largest_exe(Path(install)),
            appid=gameid,
            launch_uri=f"goggalaxy://openGameView/{gameid}",
        )


# ---------------------------------------------------------------------------
# Battle.net
# ---------------------------------------------------------------------------

# Battle.net stores installs in registry under WOW6432Node\Blizzard Entertainment.
# Each known game has a stable launch URI we can use directly.
_BNET_GAMES = {
    "WoW":          ("World of Warcraft", "battlenet://WoW"),
    "WoW_classic":  ("World of Warcraft Classic", "battlenet://WoW_classic"),
    "Pro":          ("Overwatch", "battlenet://Pro"),
    "S2":           ("StarCraft II", "battlenet://S2"),
    "S1":           ("StarCraft Remastered", "battlenet://S1"),
    "D3":           ("Diablo III", "battlenet://D3"),
    "D4":           ("Diablo IV", "battlenet://Fen"),
    "Hero":         ("Heroes of the Storm", "battlenet://Hero"),
    "WTCG":         ("Hearthstone", "battlenet://WTCG"),
}


def scan_battle_net() -> Iterator[Game]:
    base = r"SOFTWARE\WOW6432Node\Blizzard Entertainment"
    if not _enum_subkeys(winreg.HKEY_LOCAL_MACHINE, base):
        return
    for code, (name, uri) in _BNET_GAMES.items():
        path = base + "\\" + name
        install = _read_registry(winreg.HKEY_LOCAL_MACHINE, path, "InstallPath")
        if not install:
            continue
        yield Game(
            id=_safe_id(Launcher.BATTLE_NET, code),
            name=name,
            launcher=Launcher.BATTLE_NET,
            install_dir=install,
            exe_path=_largest_exe(Path(install)),
            launch_uri=uri,
            appid=code,
        )


# ---------------------------------------------------------------------------
# Riot Client
# ---------------------------------------------------------------------------

def scan_riot() -> Iterator[Game]:
    program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
    riot_root = Path(program_data) / "Riot Games"
    if not riot_root.exists():
        return
    # Look for known products
    products = {
        "league_of_legends": "League of Legends",
        "valorant": "VALORANT",
        "lor": "Legends of Runeterra",
    }
    for code, label in products.items():
        product_dir = riot_root / "Metadata" / code
        if not product_dir.exists():
            continue
        # The actual install path is in <product>.product_settings.yaml,
        # but for simplicity we just use the well-known default paths.
        guesses = [
            Path(r"C:\Riot Games") / label,
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Riot Games" / label,
        ]
        install = next((p for p in guesses if p.exists()), None)
        yield Game(
            id=_safe_id(Launcher.RIOT, code),
            name=label,
            launcher=Launcher.RIOT,
            install_dir=str(install) if install else "",
            exe_path=_largest_exe(install) if install else "",
            appid=code,
            launch_uri=f"riotclient://rso-auth/authorize?client_id={code}",
        )


# ---------------------------------------------------------------------------
# Xbox / Microsoft Store
# ---------------------------------------------------------------------------

def scan_xbox() -> Iterator[Game]:
    # Xbox / MS Store apps live under HKCU\Software\Classes\Local Settings\Software\
    # Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages — but that's
    # a heavy read. We use a friendlier path: the GamingServices DefaultLocation
    # registry key, which lists install paths for installed Xbox games.
    path = r"Software\Microsoft\GamingServices\PackageRepository\Root"
    pkgs = _enum_subkeys(winreg.HKEY_LOCAL_MACHINE, path)
    if not pkgs:
        return
    for pkg in pkgs:
        # Each pkg has another GUID-like subkey with the data; read all of them.
        sub_path = path + "\\" + pkg
        for sub in _enum_subkeys(winreg.HKEY_LOCAL_MACHINE, sub_path):
            full = sub_path + "\\" + sub
            install = _read_registry(winreg.HKEY_LOCAL_MACHINE, full, "Root")
            if not install or not Path(install).exists():
                continue
            name = Path(install).name.replace("Microsoft.", "").replace("_", " ")
            # Trim version segment
            name = re.split(r"\s+\d", name)[0].strip() or name
            yield Game(
                id=_safe_id(Launcher.XBOX, pkg),
                name=name,
                launcher=Launcher.XBOX,
                install_dir=install,
                exe_path=_largest_exe(Path(install)),
                appid=pkg,
                launch_uri=f"ms-windows-store://pdp/?productid={pkg}",
            )


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

ALL_SCANNERS = {
    "steam": scan_steam,
    "epic": scan_epic,
    "gog": scan_gog,
    "battlenet": scan_battle_net,
    "riot": scan_riot,
    "xbox": scan_xbox,
}


def scan_all() -> List[Game]:
    """Run every scanner and return the deduplicated set of games."""
    out: dict[str, Game] = {}
    for name, scan in ALL_SCANNERS.items():
        try:
            for g in scan():
                out[g.id] = g
        except Exception:
            log.exception("Scanner %s crashed", name)
    log.info("Scanned %d game(s) across %d launcher(s)", len(out), len(ALL_SCANNERS))
    return list(out.values())
