"""DNS benchmark — times common public resolvers and the user's current
ISP DNS, surfaces the fastest one with a "switch to" hint.

Pure-Python: opens a UDP socket to port 53, sends a small A query for
each test domain, measures round-trip. We time *several* domains per
resolver to average out caching effects and outliers.

Public API:

* :class:`DnsBenchmark.run()`  — async-friendly synchronous benchmark
* :class:`DnsBenchmark.run_async()` — returns a `concurrent.futures.Future`

The result is a list of :class:`DnsResult` ranked by mean RTT.
"""
from __future__ import annotations

import concurrent.futures as cf
import os
import socket
import statistics
import struct
import time
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple

from ...utils.logger import get_logger

log = get_logger("monitoring.network.dns")

# ---------------------------------------------------------------- catalogue
RECOMMENDED_DNS: List[Tuple[str, str]] = [
    # (display name, IPv4)
    ("Cloudflare 1.1.1.1",      "1.1.1.1"),
    ("Cloudflare 1.0.0.1",      "1.0.0.1"),
    ("Google 8.8.8.8",          "8.8.8.8"),
    ("Google 8.8.4.4",          "8.8.4.4"),
    ("Quad9 9.9.9.9",           "9.9.9.9"),
    ("OpenDNS 208.67.222.222",  "208.67.222.222"),
    ("Comodo 8.26.56.26",       "8.26.56.26"),
    ("AdGuard 94.140.14.14",    "94.140.14.14"),
]

DEFAULT_TEST_DOMAINS: List[str] = [
    "example.com",
    "google.com",
    "cloudflare.com",
    "github.com",
    "discord.com",
    "twitch.tv",
]


@dataclass
class DnsResult:
    label: str                            # "Cloudflare 1.1.1.1"
    server: str                           # IP address
    mean_ms: float = 0.0                  # average RTT
    min_ms: float = 0.0
    max_ms: float = 0.0
    stdev_ms: float = 0.0
    losses: int = 0                       # how many queries didn't return
    samples: List[float] = field(default_factory=list)
    is_current: bool = False              # is this the user's current DNS?

    @property
    def reachable(self) -> bool:
        return bool(self.samples)


def _build_dns_query(domain: str, *, query_id: int = 0x1337) -> bytes:
    """Minimal A-record query (no EDNS, no recursion bit gymnastics)."""
    header = struct.pack(
        ">HHHHHH",
        query_id,
        0x0100,   # standard query, recursion desired
        1, 0, 0, 0,
    )
    qname = b""
    for label in domain.encode("ascii").split(b"."):
        qname += bytes([len(label)]) + label
    qname += b"\x00"
    qtype_qclass = struct.pack(">HH", 1, 1)   # A, IN
    return header + qname + qtype_qclass


def _query_dns(server: str, domain: str, *, timeout: float = 1.5) -> Optional[float]:
    """Send a UDP DNS query, return RTT in ms or None on timeout/error."""
    msg = _build_dns_query(domain, query_id=os.getpid() & 0xFFFF)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            t0 = time.perf_counter()
            sock.sendto(msg, (server, 53))
            data, _ = sock.recvfrom(512)
            elapsed = (time.perf_counter() - t0) * 1000
            if len(data) < 4:
                return None
            # We don't validate the response payload — RTT is enough.
            return elapsed
    except (socket.timeout, OSError):
        return None


def _read_current_dns_servers() -> List[str]:
    """Best-effort: read the system's primary DNS resolvers."""
    out: List[str] = []
    # Linux/macOS — /etc/resolv.conf
    try:
        with open("/etc/resolv.conf", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip().startswith("nameserver"):
                    parts = line.split()
                    if len(parts) >= 2:
                        out.append(parts[1])
    except OSError:
        pass
    if out:
        return out
    # Windows — `Get-DnsClientServerAddress`
    try:
        import subprocess
        ps = "Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object { $_.ServerAddresses } | ForEach-Object { $_.ServerAddresses } | Select-Object -Unique"
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=4, check=False,
        )
        if res.returncode == 0 and res.stdout:
            for line in res.stdout.splitlines():
                ip = line.strip()
                if ip and "." in ip:
                    out.append(ip)
    except (FileNotFoundError, OSError):
        pass
    return out


class DnsBenchmark:
    """Benchmarks all candidate DNS servers concurrently."""

    def __init__(
        self,
        *,
        domains: Optional[Iterable[str]] = None,
        servers: Optional[Iterable[Tuple[str, str]]] = None,
        per_server_queries: int = 3,
        timeout: float = 1.5,
    ) -> None:
        self._domains = list(domains or DEFAULT_TEST_DOMAINS)
        self._servers = list(servers or RECOMMENDED_DNS)
        self._per_server_queries = max(1, per_server_queries)
        self._timeout = timeout

    def run(self) -> List[DnsResult]:
        """Synchronous benchmark — runs N parallel workers."""
        current = set(_read_current_dns_servers())
        all_servers = list(self._servers)

        # Tag the user's current DNS if it's not already in the list.
        labelled_current: List[Tuple[str, str]] = []
        for ip in current:
            if not any(s == ip for _, s in all_servers):
                labelled_current.append((f"Your DNS ({ip})", ip))
        all_servers = labelled_current + all_servers

        results: List[DnsResult] = []
        with cf.ThreadPoolExecutor(max_workers=min(8, len(all_servers))) as pool:
            futures = {
                pool.submit(self._test_server, label, ip): (label, ip)
                for label, ip in all_servers
            }
            for fut in cf.as_completed(futures):
                label, ip = futures[fut]
                try:
                    res = fut.result()
                except Exception:
                    log.exception("DNS test failed for %s", ip)
                    continue
                res.is_current = ip in current
                results.append(res)

        results.sort(key=lambda r: (not r.reachable, r.mean_ms or 1e9))
        return results

    def run_async(self) -> cf.Future:
        pool = cf.ThreadPoolExecutor(max_workers=1)
        return pool.submit(self.run)

    # ------------------------------------------------------------------ internals
    def _test_server(self, label: str, ip: str) -> DnsResult:
        result = DnsResult(label=label, server=ip)
        for domain in self._domains:
            for _ in range(self._per_server_queries):
                rtt = _query_dns(ip, domain, timeout=self._timeout)
                if rtt is None:
                    result.losses += 1
                else:
                    result.samples.append(rtt)
        if result.samples:
            result.mean_ms = statistics.mean(result.samples)
            result.min_ms = min(result.samples)
            result.max_ms = max(result.samples)
            if len(result.samples) > 1:
                result.stdev_ms = statistics.stdev(result.samples)
        return result
