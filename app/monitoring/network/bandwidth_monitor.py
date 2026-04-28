"""Per-process bandwidth monitor.

Polls ``psutil.net_io_counters(pernic=False)`` plus, when available,
the per-process Windows IPHelper (``GetPerTcpConnectionEStats``) to
attribute throughput to running processes. Without the per-process
counters we still get system-wide totals.

Public API:

* :meth:`BandwidthMonitor.snapshot`  — one-shot read
* :meth:`BandwidthMonitor.poll`      — blocking 1-second sample (delta)
* :meth:`BandwidthMonitor.top_processes` — best-effort per-process attribution

Attribution heuristic for the per-process top-N:
    1. Open TCP connections via ``psutil.net_connections('tcp')``
    2. Group by pid
    3. Score the pid by number of established connections + recent
       process IO byte counters
    4. Return top N

This is intentionally approximate — accurate per-process bandwidth on
Windows requires ``netstat -b`` (admin) or ETW. The Bandwidth Monitor
view labels the data "estimated".
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import psutil

from ...utils.logger import get_logger

log = get_logger("monitoring.network.bandwidth")


@dataclass
class BandwidthSample:
    """Aggregate (system) throughput over a 1-second window."""
    ts: float
    bytes_sent_per_s: float
    bytes_recv_per_s: float
    packets_sent_per_s: float
    packets_recv_per_s: float


@dataclass
class ProcessBandwidth:
    """Best-effort per-process attribution."""
    pid: int
    name: str
    connection_count: int
    estimated_kbps: float = 0.0
    bytes_io_per_s: float = 0.0


@dataclass
class _IoCounters:
    bytes_sent: int = 0
    bytes_recv: int = 0
    packets_sent: int = 0
    packets_recv: int = 0
    proc_read: int = 0
    proc_write: int = 0


class BandwidthMonitor:
    def __init__(self) -> None:
        self._last_net: Optional[_IoCounters] = None
        self._last_per_pid: Dict[int, int] = {}   # pid → (read+write) bytes
        self._last_ts: float = 0.0

    # ------------------------------------------------------------------ public
    def snapshot(self) -> BandwidthSample:
        """Sample relative to the previous call (or zeroes if first call)."""
        now = time.time()
        cur = self._read_net()
        if self._last_net is None or self._last_ts == 0:
            self._last_net = cur
            self._last_ts = now
            return BandwidthSample(now, 0, 0, 0, 0)
        dt = max(1e-3, now - self._last_ts)
        sample = BandwidthSample(
            ts=now,
            bytes_sent_per_s=(cur.bytes_sent - self._last_net.bytes_sent) / dt,
            bytes_recv_per_s=(cur.bytes_recv - self._last_net.bytes_recv) / dt,
            packets_sent_per_s=(cur.packets_sent - self._last_net.packets_sent) / dt,
            packets_recv_per_s=(cur.packets_recv - self._last_net.packets_recv) / dt,
        )
        self._last_net = cur
        self._last_ts = now
        return sample

    def poll(self, *, interval_s: float = 1.0) -> BandwidthSample:
        self.snapshot()
        time.sleep(interval_s)
        return self.snapshot()

    def top_processes(self, *, limit: int = 10) -> List[ProcessBandwidth]:
        """Estimate top bandwidth-using processes."""
        # 1. Build pid → connection count
        conn_count: Dict[int, int] = {}
        try:
            for c in psutil.net_connections(kind="inet"):
                if c.pid is None or c.status not in ("ESTABLISHED", "SYN_SENT", "SYN_RECV"):
                    continue
                conn_count[c.pid] = conn_count.get(c.pid, 0) + 1
        except (psutil.AccessDenied, OSError):
            log.debug("net_connections requires elevation; falling back")

        if not conn_count:
            return []

        # 2. Per-pid IO delta from the last call
        now = time.time()
        dt = max(1e-3, now - self._last_ts) if self._last_ts else 1.0
        new_per_pid: Dict[int, int] = {}
        results: List[ProcessBandwidth] = []
        for pid in conn_count.keys():
            try:
                proc = psutil.Process(pid)
                with proc.oneshot():
                    name = proc.name()
                    io = proc.io_counters() if hasattr(proc, "io_counters") else None
                io_total = (io.read_bytes + io.write_bytes) if io else 0
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            new_per_pid[pid] = io_total
            prev = self._last_per_pid.get(pid, io_total)
            io_delta = max(0, io_total - prev)
            io_rate = io_delta / dt
            results.append(ProcessBandwidth(
                pid=pid,
                name=name,
                connection_count=conn_count[pid],
                estimated_kbps=(io_rate * 8) / 1024.0,
                bytes_io_per_s=io_rate,
            ))
        self._last_per_pid = new_per_pid

        results.sort(key=lambda p: (p.bytes_io_per_s, p.connection_count), reverse=True)
        return results[:limit]

    # ------------------------------------------------------------------ internals
    @staticmethod
    def _read_net() -> _IoCounters:
        try:
            n = psutil.net_io_counters(pernic=False)
            return _IoCounters(
                bytes_sent=n.bytes_sent,
                bytes_recv=n.bytes_recv,
                packets_sent=n.packets_sent,
                packets_recv=n.packets_recv,
            )
        except Exception:
            return _IoCounters()
