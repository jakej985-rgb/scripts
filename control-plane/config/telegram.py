"""
M3TAL Telegram Configuration (v3.2 Hardened)
6-channel routing with CRLF defence and safe integer parsing.
"""

import os
import sys


# --- CRLF-Safe Helpers -------------------------------------------------------
# Windows .env files saved with CRLF endings produce tokens ending in \r.
# On Linux inside Docker this causes a 401 from the Telegram API.
# Strip aggressively at the config layer so every consumer gets clean values.

def _clean(value: str | None) -> str:
    """Strip whitespace and carriage returns from an env string."""
    return (value or "").strip().rstrip("\r\n").strip()


def _safe_int(raw: str | None, default: int = 0) -> int:
    """
    Parse an integer from an env var, stripping CRLF artefacts.
    Returns default on any parse failure rather than crashing.
    """
    cleaned = _clean(raw)
    if not cleaned:
        return default
    try:
        return int(cleaned)
    except (ValueError, TypeError) as exc:
        print(
            f"[TELEGRAM CONFIG] Could not parse int from {repr(raw)}: {exc}",
            file=sys.stderr,
        )
        return default


# --- Token (Phase 4 Hardening) -----------------------------------------------
_raw_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or ""
# Aggressive strip handles both raw spaces and \r from Windows CRLF .env
BOT_TOKEN: str | None = _raw_token.strip() or None

# Emit an early warning if the raw token had hidden whitespace so the user
# knows to fix their .env rather than spending hours debugging 401s.
if _raw_token and BOT_TOKEN != _raw_token:
    print(
        "[TELEGRAM CONFIG] WARNING: BOT_TOKEN contained leading/trailing whitespace "
        "or carriage returns — stripped automatically. "
        "Fix your .env file to silence this warning.",
        file=sys.stderr,
    )

# --- Channel Count -----------------------------------------------------------
CHAT_COUNT: int = _safe_int(
    os.getenv("TG_CHAT_COUNT") or os.getenv("TG_CHAT_MODE"),
    default=1,
)

# --- Chat IDs ----------------------------------------------------------------
MAIN_CHAT_ID: int   = _safe_int(os.getenv("TG_MAIN_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID"))
LOG_CHAT_ID: int    = _safe_int(os.getenv("TG_LOG_CHAT_ID"))
ERROR_CHAT_ID: int  = _safe_int(os.getenv("TG_ERROR_CHAT_ID"))
ALERT_CHAT_ID: int  = _safe_int(os.getenv("TG_ALERT_CHAT_ID"))
ACTION_CHAT_ID: int = _safe_int(os.getenv("TG_ACTION_CHAT_ID"))
DOCKER_CHAT_ID: int = _safe_int(os.getenv("TG_DOCKER_CHAT_ID"))

# --- Security Whitelist ------------------------------------------------------
def _parse_allowed_users(raw: str | None) -> list[int]:
    """Parse a comma-separated list of positive Telegram user IDs."""
    result: list[int] = []
    for part in (_clean(raw) or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            uid = int(part)
            if uid > 0:
                result.append(uid)
        except (ValueError, TypeError):
            print(
                f"[TELEGRAM CONFIG] Ignoring invalid ALLOWED_USERS entry: {repr(part)}",
                file=sys.stderr,
            )
    return result


ALLOWED_USERS: list[int] = _parse_allowed_users(os.getenv("ALLOWED_USERS"))

# --- Container Whitelist (Audit Fix 9) ---------------------------------------
# Static list of containers allowed to be restarted via Telegram.
# Fallback to core infrastructure if .env is not set.
ALLOWED_DOCKER_RESTARTS: list[str] = (_clean(os.getenv("ALLOWED_DOCKER_RESTARTS")) or "gluetun,traefik,m3tal-dashboard").split(",")


def is_allowed_user(user_id: int) -> bool:
    """Returns True if user_id is in the command whitelist."""
    return isinstance(user_id, int) and user_id in ALLOWED_USERS


# --- Startup Validation ------------------------------------------------------

def validate() -> bool:
    """
    Validates the Telegram configuration at startup.
    Prints diagnostics and returns False if the system cannot function.
    """
    print(f"[TELEGRAM] Validating {CHAT_COUNT}-channel configuration...")
    ok = True

    if not BOT_TOKEN:
        print(
            "[TELEGRAM] CRITICAL: BOT_TOKEN is missing or empty.\n"
            "  Set TELEGRAM_BOT_TOKEN in your .env file.\n"
            "  If on Linux, ensure the .env file uses LF line endings (not CRLF).",
            file=sys.stderr,
        )
        ok = False

    if not (1 <= CHAT_COUNT <= 6):
        print(
            f"[TELEGRAM] CRITICAL: TG_CHAT_COUNT must be 1-6, got {CHAT_COUNT}.",
            file=sys.stderr,
        )
        ok = False

    if MAIN_CHAT_ID == 0:
        print(
            "[TELEGRAM] CRITICAL: TG_MAIN_CHAT_ID (or TELEGRAM_CHAT_ID) is required.",
            file=sys.stderr,
        )
        ok = False

    # Soft warnings for optional channels
    _channel_requirements = [
        (2, "TG_ERROR_CHAT_ID",  ERROR_CHAT_ID),
        (3, "TG_LOG_CHAT_ID",    LOG_CHAT_ID),
        (4, "TG_ALERT_CHAT_ID",  ALERT_CHAT_ID),
        (5, "TG_ACTION_CHAT_ID", ACTION_CHAT_ID),
        (6, "TG_DOCKER_CHAT_ID", DOCKER_CHAT_ID),
    ]
    for required_count, var_name, value in _channel_requirements:
        if CHAT_COUNT >= required_count and value == 0:
            print(
                f"[TELEGRAM] WARNING: {var_name} is required for "
                f"CHAT_COUNT >= {required_count} but is 0. "
                "Messages for this channel will fall back to MAIN_CHAT_ID.",
                file=sys.stderr,
            )

    if not ALLOWED_USERS:
        print(
            "[TELEGRAM] WARNING: No ALLOWED_USERS configured. "
            "/docker restart and other commands will be disabled.",
            file=sys.stderr,
        )

    if ok:
        print(
            f"[TELEGRAM] Configuration valid. "
            f"Channels: {CHAT_COUNT}, Allowed users: {len(ALLOWED_USERS)}",
        )
    return ok


def diagnose_token() -> str:
    """
    Returns a human-readable diagnostic string for the current token state.
    Useful for debugging 401 errors.
    """
    raw = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or ""
    lines = [
        f"  Raw env length : {len(raw)}",
        f"  Cleaned length : {len(BOT_TOKEN) if BOT_TOKEN else 0}",
        f"  Starts with    : {repr(raw[:12]) if raw else 'N/A'}",
        f"  Ends with      : {repr(raw[-6:]) if raw else 'N/A'}",
        f"  Has \\r         : {chr(13) in raw}",
        f"  Has \\n         : {chr(10) in raw}",
        f"  Has spaces     : {' ' in raw}",
        f"  BOT_TOKEN set  : {BOT_TOKEN is not None}",
    ]
    return "Token diagnostics:\n" + "\n".join(lines)
