"""
M3TAL Telegram Session Store (v4.0)
Lightweight in-memory per-user state for multi-step command flows.

Sessions auto-expire after TIMEOUT seconds. No persistence — if the bot
restarts, users just tap the button again.
"""

import time

TIMEOUT = 300  # 5 minutes

_sessions: dict[int, dict] = {}


def get(user_id: int) -> dict | None:
    """Return the session for user_id, or None if expired/missing."""
    entry = _sessions.get(user_id)
    if entry is None:
        return None
    if time.time() - entry.get("_ts", 0) > TIMEOUT:
        clear(user_id)
        return None
    return entry


def set(user_id: int, data: dict) -> None:
    """Store session data for user_id with a fresh timestamp."""
    data["_ts"] = time.time()
    _sessions[user_id] = data


def clear(user_id: int) -> None:
    """Remove the session for user_id."""
    _sessions.pop(user_id, None)


def _prune() -> None:
    """Remove all expired sessions (called periodically)."""
    now = time.time()
    expired = [uid for uid, data in _sessions.items()
               if now - data.get("_ts", 0) > TIMEOUT]
    for uid in expired:
        del _sessions[uid]
