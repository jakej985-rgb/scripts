import requests
from config.telegram import BOT_TOKEN

# M3TAL Telegram Router (Audit Phase 4)
# Minimal dependency architecture using 'requests'

def send(chat_id: int, message: str) -> bool:
    """Synchronous send using requests with timeout (Audit Fix 5.2)."""
    if not BOT_TOKEN or not chat_id:
        return False
        
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        # User Fix: Add timeout to prevent hanging threads
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code == 200:
            return True
        else:
            # Common failure: status 400 (bad chat id), 401 (bad token), 429 (rate limit)
            print(f"[TELEGRAM FAIL] {resp.status_code}: {resp.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"[TELEGRAM CONN FAIL] {e}")
        return False
    except Exception as e:
        print(f"[TELEGRAM UNEXPECTED FAIL] {e}")
        return False
