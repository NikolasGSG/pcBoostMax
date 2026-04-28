"""Windows-friendly subprocess helpers.

Every subprocess call in the app MUST go through here. Two reasons:

1. ``CREATE_NO_WINDOW`` is always set so console helpers (powercfg, reg, sc,
   PowerShell, PresentMon) never flash a black window on the user's screen.
   That flash is one of the top things that makes a legitimate optimizer
   *feel* like malware.

2. We also set a sensible default timeout + capture_output so every caller
   gets consistent stdout / stderr handling.

The module deliberately has **zero imports from the rest of the app** so it
can be used from any layer (core, rules, UI, safety) without cycles.
"""
from __future__ import annotations

import subprocess
import sys
from typing import Optional, Sequence

# Windows CreateProcess flag that hides the console window for the child.
# 0x08000000 == CREATE_NO_WINDOW (winbase.h). Evaluated once at import.
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def run(
    cmd: Sequence[str],
    *,
    timeout: float = 15.0,
    text: bool = True,
    input_: Optional[str] = None,
) -> tuple[int, str, str]:
    """Run ``cmd`` without ever flashing a console window.

    Returns ``(returncode, stdout, stderr)``. On any exception returns
    ``(-1, "", str(exc))`` so the caller can log the failure without having
    to wrap every invocation in its own try/except.
    """
    try:
        cp = subprocess.run(
            list(cmd),
            capture_output=True,
            text=text,
            timeout=timeout,
            input=input_,
            creationflags=_CREATE_NO_WINDOW,
            # Inherit parent env so PATH/SystemRoot are available
            # even when launched from a frozen PyInstaller exe.
        )
        return cp.returncode, cp.stdout or "", cp.stderr or ""
    except subprocess.TimeoutExpired as exc:
        return -1, "", f"timeout after {exc.timeout}s"
    except Exception as exc:  # pragma: no cover - last-ditch guard
        return -1, "", str(exc)


def popen(
    cmd: Sequence[str],
    *,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    text: bool = True,
    bufsize: int = 1,
) -> subprocess.Popen:
    """Launch a long-running process (e.g. PresentMon) without a window.

    Use this for streaming helpers where the caller wants to read stdout
    incrementally instead of blocking until completion.
    """
    return subprocess.Popen(
        list(cmd),
        stdout=stdout,
        stderr=stderr,
        text=text,
        bufsize=bufsize,
        creationflags=_CREATE_NO_WINDOW,
    )


# Re-export the flag for callers that use subprocess directly and just need
# the constant (we prefer they use run() / popen(), but this is handy for
# quick cases such as shell= invocations we'd rather keep centralised).
CREATE_NO_WINDOW: int = _CREATE_NO_WINDOW
