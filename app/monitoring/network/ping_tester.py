"""Ping common game-server endpoints to surface the lowest-latency region.

We avoid the ``ping`` shell command — too brittle on Windows. Instead we
do a TCP handshake to port 443 (or a known game-server port) and measure
the time until the SYN-ACK comes back. That's a reliable per-region RTT
that doesn't depend on ICMP being allowed.
"""
from __future__ import annotations

import concurrent.futures as cf
import socket
import statistics
import time
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple

from ...utils.logger import get_logger

log = get_logger("monitoring.network.ping")


@dataclass
class PingTarget:
    label: str       # display name e.g. "Valorant — EU West"
    host: str        # hostname to resolve & connect
    port: int = 443  # TCP port; 443 works for almost all CDN-fronted endpoints


# Curated regional endpoints. Most are HTTPS-fronted matchmaking or
# patch endpoints — pinging them gives a very good proxy for game-server
# latency from the user's network.
GAME_SERVERS: List[PingTarget] = [
    PingTarget("Valorant — EU West",      "dyn.riotcdn.net"),
    PingTarget("Valorant — NA East",      "valorant.secure.dyn.riotcdn.net"),
    PingTarget("League of Legends — EUW", "lolclient.lol.riotgames.com"),
    PingTarget("CS2 — Steam Frankfurt",   "valve.akamai.steamstatic.com"),
    PingTarget("Fortnite — EU",           "ol.epicgames.com"),
    PingTarget("Apex — EA East",          "accounts.ea.com"),
    PingTarget("Battle.net — EU",         "eu.battle.net"),
    PingTarget("Battle.net — US",         "us.battle.net"),
    PingTarget("Discord — Voice",         "gateway.discord.gg"),
    PingTarget("Cloudflare PoP",          "1.1.1.1", 443),
    PingTarget("Google PoP",              "8.8.8.8", 443),
]


@dataclass
class PingResult:
    target: PingTarget
    samples_ms: List[float] = field(default_factory=list)
    losses: int = 0
    error: Optional[str] = None

    @property
    def reachable(self) -> bool:
        return bool(self.samples_ms)

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.samples_ms) if self.samples_ms else 0.0

    @property
    def min_ms(self) -> float:
        return min(self.samples_ms) if self.samples_ms else 0.0

    @property
    def max_ms(self) -> float:
        return max(self.samples_ms) if self.samples_ms else 0.0

    @property
    def jitter_ms(self) -> float:
        return statistics.stdev(self.samples_ms) if len(self.samples_ms) > 1 else 0.0

    def quality_band(self) -> str:
        """Return 'excellent' | 'good' | 'fair' | 'poor' | 'unreachable'."""
        if not self.reachable:
            return "unreachable"
        m = self.mean_ms
        if m < 25:    return "excellent"
        if m < 60:    return "good"
        if m < 120:   return "fair"
        return "poor"


def _tcp_ping(host: str, port: int, *, timeout: float = 2.0) -> Optional[float]:
    try:
        addr_info = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        if not addr_info:
            return None
        family, sock_type, proto, _, sockaddr = addr_info[0]
    except socket.gaierror:
        return None
    sock = socket.socket(family, sock_type, proto)
    sock.settimeout(timeout)
    t0 = time.perf_counter()
    try:
        sock.connect(sockaddr)
        return (time.perf_counter() - t0) * 1000
    except (socket.timeout, OSError):
        return None
    finally:
        try:
            sock.close()
        except OSError:
            pass


class PingTester:
    """Run TCP-based pings against a list of targets in parallel."""

    def __init__(
        self,
        *,
        targets: Optional[Iterable[PingTarget]] = None,
        attempts: int = 4,
        timeout: float = 2.0,
    ) -> None:
        self._targets = list(targets or GAME_SERVERS)
        self._attempts = max(1, attempts)
        self._timeout = timeout

    def run(self) -> List[PingResult]:
        results: List[PingResult] = []
        with cf.ThreadPoolExecutor(max_workers=min(8, len(self._targets) or 1)) as pool:
            futs = {pool.submit(self._probe, t): t for t in self._targets}
            for fut in cf.as_completed(futs):
                target = futs[fut]
                try:
                    results.append(fut.result())
                except Exception as exc:
                    log.exception("ping failed for %s", target.host)
                    results.append(PingResult(target=target, error=str(exc)))
        results.sort(key=lambda r: (not r.reachable, r.mean_ms or 1e9))
        return results

    def run_async(self) -> cf.Future:
        pool = cf.ThreadPoolExecutor(max_workers=1)
        return pool.submit(self.run)

    def _probe(self, target: PingTarget) -> PingResult:
        result = PingResult(target=target)
        for _ in range(self._attempts):
            rtt = _tcp_ping(target.host, target.port, timeout=self._timeout)
            if rtt is None:
                result.losses += 1
            else:
                result.samples_ms.append(rtt)
        return result
