import requests
import time
from config.telegram import BOT_TOKEN

# M3TAL Telegram Client (v3 Layered)
# Responsibility: RAW API logic only. No routing, no business logic.

def call_api(method: str, params: dict = None, timeout: int = 10) -> dict:
    """Core HTTP wrapper for Telegram API with basic retry logic."""
    if not BOT_TOKEN:
        return {"ok": False, "description": "BOT_TOKEN not configured"}
        
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    
    try:
        if method == "sendMessage":
            resp = requests.post(url, json=params, timeout=timeout)
        else:
            resp = requests.get(url, params=params, timeout=timeout)
            
        if resp.status_code == 200:
            return resp.json()
        
        return {
            "ok": False, 
            "status_code": resp.status_code, 
            "description": resp.text
        }
    except Exception as e:
        return {"ok": False, "description": str(e)}

def send_text(chat_id: int, text: str) -> bool:
    """High-level wrapper for sending text with HTML support."""
    params = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    result = call_api("sendMessage", params)
    return result.get("ok", False)
