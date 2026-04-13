import requests
import time
import random
from config.telegram import BOT_TOKEN

# M3TAL Telegram Client (v3.1 Hardened)
# Responsibility: RAW API logic with strict retry/backoff policies.

MAX_RETRIES = 3
BASE_BACKOFF = 1.0 # seconds

# Observability Counters
stats = {
    "sent": 0,
    "failed": 0,
    "retries": 0,
    "last_error": None
}

def get_stats():
    """Returns a copy of the current metrics."""
    return stats.copy()

    """Core HTTP wrapper with Exponential Backoff and 429 handling."""
    if not BOT_TOKEN:
        return {"ok": False, "description": "BOT_TOKEN not configured"}
        
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    
    for attempt in range(MAX_RETRIES):
        try:
            if method == "sendMessage":
                resp = requests.post(url, json=params, timeout=timeout)
            else:
                resp = requests.get(url, params=params, timeout=timeout)
                
            if resp.status_code == 200:
                stats["sent"] += 1
                return resp.json()
            
            # --- Retry Logic ---
            stats["retries"] += 1
            if resp.status_code == 429: # Rate Limit
                retry_after = 30 # Default if header missing
                try: retry_after = int(resp.json().get("parameters", {}).get("retry_after", 30))
                except: pass
                print(f"[TELEGRAM] Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)
                continue # Try again
                
            if resp.status_code >= 500: # Server Error
                backoff = (BASE_BACKOFF * (2 ** attempt)) + random.uniform(0.1, 0.5)
                time.sleep(backoff)
                continue
                
            # Hard Fails (400, 401, 404) - Do NOT retry
            stats["failed"] += 1
            stats["last_error"] = f"{resp.status_code}: {resp.text}"
            return {
                "ok": False, 
                "status_code": resp.status_code, 
                "description": resp.text
            }
            
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            # Network issue - Retry with backoff
            stats["retries"] += 1
            backoff = (BASE_BACKOFF * (2 ** attempt)) + random.uniform(0.1, 0.5)
            time.sleep(backoff)
            
    stats["failed"] += 1
    stats["last_error"] = "Max retries exceeded"
    return {"ok": False, "description": "Max retries exceeded"}

def send_text(chat_id: int, text: str) -> bool:
    """High-level wrapper for sending text with HTML support."""
    params = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    result = call_api("sendMessage", params)
    return result.get("ok", False)
