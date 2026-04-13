from . import client
from . import tg_queue
import hashlib
from collections import deque
from config.telegram import (
    CHAT_COUNT, MAIN_CHAT_ID, LOG_CHAT_ID, ERROR_CHAT_ID, 
    ALERT_CHAT_ID, ACTION_CHAT_ID, DOCKER_CHAT_ID
)

# M3TAL Telegram Router (v3.2 Hardened)
# Responsibility: Business logic, channel routing, and deduplication.

# Deduplication State (Last 50 unique messages)
_sent_hashes = deque(maxlen=50)

def _is_duplicate(text: str) -> bool:
    """Checks if the message has been sent recently to avoid spam."""
    m_hash = hashlib.sha256(text.encode()).hexdigest()
    if m_hash in _sent_hashes:
        return True
    _sent_hashes.append(m_hash)
    return False

def route_message(channel: str, text: str):
    """Routes a message to the appropriate chat ID with deduplication check."""
    if _is_duplicate(text):
        return
        
    target_chat = MAIN_CHAT_ID # Default fallback
    
    if channel == "log" and CHAT_COUNT >= 3 and LOG_CHAT_ID:
        target_chat = LOG_CHAT_ID
    elif channel == "error" and CHAT_COUNT >= 2 and ERROR_CHAT_ID:
        target_chat = ERROR_CHAT_ID
    elif channel == "alert" and CHAT_COUNT >= 4 and ALERT_CHAT_ID:
        target_chat = ALERT_CHAT_ID
    elif channel == "action" and CHAT_COUNT >= 5 and ACTION_CHAT_ID:
        target_chat = ACTION_CHAT_ID
    elif channel == "docker" and CHAT_COUNT == 6 and DOCKER_CHAT_ID:
        target_chat = DOCKER_CHAT_ID
        
    tg_queue.enqueue(target_chat, text)

def get_new_updates(offset: int = 0):
    """Wrapper for fetching updates via the client."""
    params = {"offset": offset + 1, "timeout": 10}
    result = client.call_api("getUpdates", params)
    return result.get("result", []) if result.get("ok") else []
