"""
M3TAL Telegram Client (v3.2 Hardened)
Responsibility: Raw API calls with retry, backoff, and 429 handling.
"""

import sys
import time
import random
import requests

# --- Token Loading with CRLF Defence ----------------------------------------
# Trailing \r from Windows CRLF .env files causes 401 on Linux.
# We strip here at the lowest level so every other layer gets a clean token.

try:
    from config.telegram import BOT_TOKEN as _RAW_TOKEN
    BOT_TOKEN: str | None = (_RAW_TOKEN or "").strip() or None
except Exception as _cfg_err:
    BOT_TOKEN = None
    print(
        f"[TELEGRAM CLIENT] Failed to load config: {_cfg_err}",
        file=sys.stderr,
    )

# --- Constants ----------------------------------------------------------------
MAX_RETRIES  = 3
BASE_BACKOFF = 1.0  # seconds

# --- Observability ------------------------------------------------------------
_stats: dict[str, object] = {
    "sent":       0,
    "failed":     0,
    "retries":    0,
    "last_error": None,
    "last_ok_ts": None,
}


def get_stats() -> dict:
    """Returns a snapshot of send metrics."""
    return _stats.copy()


def _record_success() -> None:
    _stats["sent"] += 1
    _stats["last_ok_ts"] = time.time()


def _record_failure(reason: str) -> None:
    _stats["failed"] += 1
    _stats["last_error"] = reason


def _record_retry() -> None:
    _stats["retries"] += 1


# --- Core API Call -----------------------------------------------------------

def call_api(
    method: str,
    params: dict | None = None,
    timeout: int = 10,
) -> dict:
    """
    Core HTTP wrapper with exponential backoff and 429 handling.

    Returns a dict with at minimum {"ok": bool}.
    Never raises — all exceptions are caught and returned as {"ok": False, ...}.
    """
    if not BOT_TOKEN:
        msg = "BOT_TOKEN not configured or empty"
        _record_failure(msg)
        return {"ok": False, "description": msg}

    if params is None:
        params = {}

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

    for attempt in range(MAX_RETRIES):
        try:
            if method == "sendMessage":
                resp = requests.post(url, json=params, timeout=timeout)
            else:
                resp = requests.get(url, params=params, timeout=timeout)

            # ── Success ──────────────────────────────────────────────────────
            if resp.status_code == 200:
                _record_success()
                return resp.json()

            # ── Rate Limited (429) ────────────────────────────────────────────
            if resp.status_code == 429:
                _record_retry()
                retry_after = 30
                try:
                    retry_after = int(
                        resp.json()
                        .get("parameters", {})
                        .get("retry_after", 30)
                    )
                except Exception:
                    pass
                print(
                    f"[TELEGRAM] Rate limited on {method}. "
                    f"Waiting {retry_after}s... (attempt {attempt + 1}/{MAX_RETRIES})",
                    file=sys.stderr,
                )
                time.sleep(retry_after)
                continue

            # ── Server Error (5xx) ────────────────────────────────────────────
            if resp.status_code >= 500:
                _record_retry()
                backoff = (BASE_BACKOFF * (2 ** attempt)) + random.uniform(0.1, 0.5)
                print(
                    f"[TELEGRAM] Server error {resp.status_code} on {method}. "
                    f"Retrying in {backoff:.1f}s...",
                    file=sys.stderr,
                )
                time.sleep(backoff)
                continue

            # ── Hard Fail (4xx) — do NOT retry ────────────────────────────────
            # 401 most commonly means a CRLF-corrupted token on Linux.
            if resp.status_code == 401:
                detail = (
                    "401 Unauthorized. If running on Linux, check for Windows CRLF "
                    "line endings in your .env file (token may contain \\r). "
                    f"Token length received: {len(BOT_TOKEN)}, "
                    f"ends with: {repr(BOT_TOKEN[-4:]) if BOT_TOKEN else 'N/A'}"
                )
            else:
                detail = f"{resp.status_code}: {resp.text[:200]}"

            _record_failure(detail)
            print(f"[TELEGRAM] Hard fail on {method}: {detail}", file=sys.stderr)
            return {"ok": False, "status_code": resp.status_code, "description": detail}

        except requests.exceptions.Timeout:
            _record_retry()
            backoff = (BASE_BACKOFF * (2 ** attempt)) + random.uniform(0.1, 0.5)
            print(
                f"[TELEGRAM] Timeout on {method} (attempt {attempt + 1}/{MAX_RETRIES}). "
                f"Retrying in {backoff:.1f}s...",
                file=sys.stderr,
            )
            time.sleep(backoff)

        except requests.exceptions.ConnectionError as exc:
            _record_retry()
            backoff = (BASE_BACKOFF * (2 ** attempt)) + random.uniform(0.1, 0.5)
            print(
                f"[TELEGRAM] Connection error on {method} : {exc} "
                f"(attempt {attempt + 1}/{MAX_RETRIES}). Retrying in {backoff:.1f}s...",
                file=sys.stderr,
            )
            time.sleep(backoff)

        except requests.exceptions.RequestException as exc:
            # Catch-all for other requests errors (SSL, invalid URL, etc.)
            reason = f"RequestException on {method}: {exc}"
            _record_failure(reason)
            print(f"[TELEGRAM] {reason}", file=sys.stderr)
            return {"ok": False, "description": reason}

        except Exception as exc:
            # Unexpected error — don't retry, surface immediately
            reason = f"Unexpected error on {method}: {exc}"
            _record_failure(reason)
            print(f"[TELEGRAM] {reason}", file=sys.stderr)
            return {"ok": False, "description": reason}

    # All retries exhausted
    reason = f"Max retries ({MAX_RETRIES}) exceeded for {method}"
    _record_failure(reason)
    print(f"[TELEGRAM] {reason}", file=sys.stderr)
    return {"ok": False, "description": reason}


# --- High-Level Helpers ------------------------------------------------------

def send_text(chat_id: int, text: str) -> bool:
    """
    Sends a plain HTML-formatted message to chat_id.
    Returns True on success, False on any failure.
    """
    if not chat_id or chat_id == 0:
        return False

    # Telegram hard limit is 4096 chars
    if len(text) > 4096:
        text = text[:4080] + "\n... [truncated]"

    result = call_api(
        "sendMessage",
        {"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
    )
    return bool(result.get("ok"))


def get_updates(offset: int = 0, timeout: int = 10) -> list[dict]:
    """
    Fetches new updates from the Bot API.
    Returns a list of update dicts, or empty list on any failure.
    """
    result = call_api(
        "getUpdates",
        {"offset": offset + 1, "timeout": timeout},
        timeout=timeout + 5,
    )
    if not result.get("ok"):
        return []
    updates = result.get("result", [])
    if not isinstance(updates, list):
        return []
    return updates
