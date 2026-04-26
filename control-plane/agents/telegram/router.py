from . import client
from . import tg_queue
import hashlib
from config.telegram import (
    CHAT_COUNT, MAIN_CHAT_ID, LOG_CHAT_ID, ERROR_CHAT_ID, 
    ALERT_CHAT_ID, ACTION_CHAT_ID, DOCKER_CHAT_ID
)

# M3TAL Telegram Router (v3.2 Hardened)
# Responsibility: Business logic, channel routing, and deduplication.

import time
import re

# Deduplication State (Last 5 minutes of unique messages - Audit Fix H7.12)
_sent_hashes = {} # {hash: {"ts": timestamp, "count": int}}
DEDUP_TTL = 300   # 5 minutes
ESCALATION_THRESHOLD = 5 # Re-alert after 5 suppressed duplicates

def _strip_html(text: str) -> str:
    """Removes HTML tags for cleaner hashing (Audit Fix 18)."""
    return re.sub(r'<[^>]+>', '', text)

def _is_duplicate(text: str) -> bool:
    """Checks if the message has been sent recently to avoid spam (TTL based).
    Escalation (Audit Fix M4): Allow re-alert after N suppressions.
    """
    now = time.time()
    clean_text = _strip_html(text)
    
    # Audit Fix M4: Normalize dynamic fields (timestamps, counts) for better dedup
    # Remove timestamps like 06:06:00 or 2026-04-23 06:06:00
    norm_text = re.sub(r'\d{2}:\d{2}:\d{2}', 'HH:MM:SS', clean_text)
    norm_text = re.sub(r'\d{4}-\d{2}-\d{2}', 'YYYY-MM-DD', norm_text)
    # Remove numbers that likely represent counts or IDs
    norm_text = re.sub(r'\b\d+\b', 'N', norm_text)
    
    m_hash = hashlib.sha256(norm_text.encode()).hexdigest()
    
    # 1. Prune expired hashes
    to_delete = [h for h, data in _sent_hashes.items() if (now - data["ts"]) > DEDUP_TTL]
    for h in to_delete:
        del _sent_hashes[h]

    # 2. Duplicate check & Escalation
    if m_hash in _sent_hashes:
        _sent_hashes[m_hash]["count"] += 1
        if _sent_hashes[m_hash]["count"] >= ESCALATION_THRESHOLD:
            # Escalate: Reset counter and timestamp to allow this one through
            _sent_hashes[m_hash]["count"] = 0
            _sent_hashes[m_hash]["ts"] = now
            return False
        return True
    
    _sent_hashes[m_hash] = {"ts": now, "count": 0}
    return False

# Audit Fix M4: Outbound Rate Limiting (10 msgs / 60s per channel)
_channel_rate_limits = {}
MAX_PER_MINUTE = 10

def _is_rate_limited(chat_id: int) -> bool:
    now = time.time()
    if chat_id not in _channel_rate_limits:
        _channel_rate_limits[chat_id] = []
    
    # Prune timestamps older than 60s
    _channel_rate_limits[chat_id] = [ts for ts in _channel_rate_limits[chat_id] if now - ts < 60]
    
    if len(_channel_rate_limits[chat_id]) >= MAX_PER_MINUTE:
        return True
        
    _channel_rate_limits[chat_id].append(now)
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
        
    # Audit Fix M4: Final rate limit check before enqueue
    if _is_rate_limited(target_chat):
        # We don't log this to the channel (to avoid more noise), but we can log to console
        # print(f"[ROUTER] Rate limiting channel {target_chat}")
        return

    tg_queue.enqueue(target_chat, text)

def get_new_updates(offset: int = 0):
    """Wrapper for fetching updates via the client with long-polling (v3.3)."""
    return client.get_updates(offset, timeout=20)
