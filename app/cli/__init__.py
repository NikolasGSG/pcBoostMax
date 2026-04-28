"""Headless command-line entry-points for GameBoost.

The CLI lets power users + scripts run optimizations, diagnostics and
benchmarks without launching the Qt GUI. It's a pure subset of the
existing services — no separate code paths.

Usage examples::

    GameBoost --cli optimize --plan max-perf --apply
    GameBoost --cli diagnose stutter
    GameBoost --cli bench dns
    GameBoost --cli bench ping
    GameBoost --cli inspect drivers
    GameBoost --cli rollback last

All commands print plain text to stdout and exit with a non-zero status
on failure so they can be piped from scripts.
"""
from .runner import build_parser, run_cli

__all__ = ["build_parser", "run_cli"]
