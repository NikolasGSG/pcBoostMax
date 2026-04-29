"""Headless command-line entry-points for GameBoostApex.

The CLI lets power users + scripts run optimizations, diagnostics and
benchmarks without launching the Qt GUI. It's a pure subset of the
existing services — no separate code paths.

Usage examples::

    GameBoostApex --cli optimize --plan max-perf --apply
    GameBoostApex --cli diagnose stutter
    GameBoostApex --cli bench dns
    GameBoostApex --cli bench ping
    GameBoostApex --cli inspect drivers
    GameBoostApex --cli rollback last

All commands print plain text to stdout and exit with a non-zero status
on failure so they can be piped from scripts.
"""
from .runner import build_parser, run_cli

__all__ = ["build_parser", "run_cli"]
