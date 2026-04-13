"""
M3TAL Telegram Package (v3.2)
Exposes the public service API. Import this package, not individual submodules.

Usage:
    from agents import telegram
    telegram.start()
    telegram.alert("Something is on fire")
    telegram.send_direct(chat_id, "Direct message")
"""

import sys

# --- Guarded service import --------------------------------------------------
# The service layer depends on config.telegram being importable.
# If the config is missing or broken we degrade gracefully so every other
# agent still boots even when Telegram is misconfigured.

try:
    from .service import (
        start,
        stop,
        send_main,
        send_direct,
        log,
        error,
        alert,
        action,
        docker,
    )
    _AVAILABLE = True
except ImportError as _e:
    _AVAILABLE = False
    _IMPORT_ERROR = str(_e)

    def _noop(*args, **kwargs):
        pass

    def _warn(*args, **kwargs):
        print(
            f"[TELEGRAM] Subsystem unavailable (import error: {_IMPORT_ERROR}). "
            "Message dropped.",
            file=sys.stderr,
        )

    start     = _noop
    stop      = _noop
    send_main = _warn
    send_direct = _warn
    log       = _warn
    error     = _warn
    alert     = _warn
    action    = _warn
    docker    = _warn

except Exception as _e:
    _AVAILABLE = False

    def _critical(*args, **kwargs):
        print(
            f"[TELEGRAM] CRITICAL: Unexpected error loading subsystem: {_e}. "
            "Message dropped.",
            file=sys.stderr,
        )

    start = stop = send_main = send_direct = _critical
    log = error = alert = action = docker = _critical


def is_available() -> bool:
    """Returns True if the Telegram subsystem loaded without errors."""
    return _AVAILABLE
