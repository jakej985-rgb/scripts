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

_AVAILABLE = False
_error_msg = "Unknown error"

try:
    from .service import (
        start, stop, send_main, send_direct,
        log, error, alert, action, docker,
        send_keyboard, answer_callback,
    )
    from . import router # Audit Fix: Explicit export for command_listener
    _AVAILABLE = True
except ImportError as e:
    _error_msg = f"Import error: {e}"
except Exception as e:
    _error_msg = f"Unexpected error: {e}"

if not _AVAILABLE:
    def _fail_log(*args, **kwargs):
        print(f"[TELEGRAM] Subsystem unavailable ({_error_msg}). Message dropped.", file=sys.stderr)

    start = stop = _fail_log
    send_main = send_direct = log = error = alert = action = docker = _fail_log
    send_keyboard = answer_callback = _fail_log


def is_available() -> bool:
    """Returns True if the Telegram subsystem loaded without errors."""
    return _AVAILABLE
