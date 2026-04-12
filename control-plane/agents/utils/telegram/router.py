import requests
import os
from config.telegram import BOT_TOKEN
from .paths import TELEGRAM_OFFSET_TXT

# M3TAL Telegram Router (v2 Hardened)
# Minimal dependency architecture with persistent offset tracking

def send(chat_id: int, message: str) -> bool:
    """Synchronous send using requests with 5s timeout."""
    if not BOT_TOKEN or not chat_id:
        return False
        
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code == 200:
            return True
        else:
            print(f"[TELEGRAM FAIL] {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"[TELEGRAM SEND ERR] {e}")
        return False

def save_offset(offset: int):
    """Persist the last processed update ID."""
    try:
        with open(TELEGRAM_OFFSET_TXT, "w") as f:
            f.write(str(offset))
    except Exception as e:
        print(f"[TELEGRAM OFFSET SAVE ERR] {e}")

def load_offset() -> int:
    """Load the last processed update ID from state."""
    if not TELEGRAM_OFFSET_TXT.exists():
        return 0
    try:
        with open(TELEGRAM_OFFSET_TXT, "r") as f:
            return int(f.read().strip())
    except:
        return 0

def initialize_offset() -> int:
    """Discard all history by jumping to the latest update ID on startup."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    try:
        # Use longer timeout for polling
        resp = requests.get(url, timeout=10).json()
        if resp.get("result"):
            latest_id = resp["result"][-1]["update_id"]
            save_offset(latest_id)
            return latest_id
    except Exception as e:
        print(f"[TELEGRAM OFFSET INIT ERR] {e}")
    return 0

def get_updates(timeout=10):
    """Generator yielding new updates while tracking the offset."""
    current_offset = load_offset()
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"offset": current_offset + 1, "timeout": timeout}
    
    try:
        resp = requests.get(url, params=params, timeout=timeout + 5).json()
        for update in resp.get("result", []):
            new_id = update["update_id"]
            save_offset(new_id)
            yield update
    except Exception as e:
        # Don't spam console on transient network issues
        pass

def discover_chats() -> dict:
    """
    Scans recent updates for #m3tal_ keywords to map chat IDs.
    Keywords: #m3tal_main, #m3tal_logs, #m3tal_error, #m3tal_alert, #m3tal_action, #m3tal_docker
    """
    KEYWORDS = {
        "TG_MAIN_CHAT_ID": "#m3tal_main",
        "TG_LOG_CHAT_ID": "#m3tal_logs",
        "TG_ERROR_CHAT_ID": "#m3tal_error",
        "TG_ALERT_CHAT_ID": "#m3tal_alert",
        "TG_ACTION_CHAT_ID": "#m3tal_action",
        "TG_DOCKER_CHAT_ID": "#m3tal_docker"
    }
    
    mapping = {}
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    try:
        resp = requests.get(url, timeout=10).json()
        for update in resp.get("result", []):
            msg = update.get("message", {})
            text = msg.get("text", "").lower()
            chat_id = msg.get("chat", {}).get("id")
            
            if not text or not chat_id:
                continue
                
            for env_key, tag in KEYWORDS.items():
                if tag in text:
                    mapping[env_key] = chat_id
                    print(f"[DISCOVERY] Found {tag} in chat {chat_id}")
                    
    except Exception as e:
        print(f"[DISCOVERY ERR] {e}")
        
    return mapping
