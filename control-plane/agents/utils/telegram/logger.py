from config.telegram import (
    CHAT_MODE, MAIN_CHAT_ID, LOG_CHAT_ID, ERROR_CHAT_ID, ALERT_CHAT_ID
)
from .queue import enqueue

# M3TAL Telegram Dynamic Logger (Audit Phase 4)
# Configurable multi-channel routing with anti-spam hooks

def should_send(key: str, cooldown: int = 10) -> bool:
    """Future Throttling Hook (Audit Fix 5.5)."""
    # Currently permits all messages. 
    # Scalable to Redis/Memory-based deduplication in next phase.
    return True

def _push(chat_id: int, msg: str):
    if chat_id != 0:
        enqueue(chat_id, msg)

def log(msg: str):
    """Normal operations routing."""
    if not should_send("log"): return
    
    if CHAT_MODE == 1:
        _push(MAIN_CHAT_ID, f"⚪ <b>[LOG]</b> {msg}")
    elif CHAT_MODE >= 3:
        _push(LOG_CHAT_ID, f"⚪ <b>[LOG]</b> {msg}")
    else:
        # Mode 2 maps logs back to main
        _push(MAIN_CHAT_ID, f"⚪ <b>[LOG]</b> {msg}")

def error(msg: str):
    """Failures routing."""
    if not should_send("error"): return
    
    if CHAT_MODE == 1:
        _push(MAIN_CHAT_ID, f"🔴 <b>[ERROR]</b> {msg}")
    else:
        # Mode 2, 3, 4 route errors to dedicated channel
        target = ERROR_CHAT_ID if ERROR_CHAT_ID != 0 else MAIN_CHAT_ID
        _push(target, f"🔴 <b>[ERROR]</b> {msg}")

def alert(msg: str):
    """Critical issues routing."""
    if not should_send("alert"): return
    
    if CHAT_MODE == 4:
        _push(ALERT_CHAT_ID, f"🚨 <b>[ALERT]</b> {msg}")
    elif CHAT_MODE >= 2:
        # Route alerts to error channel in modes 2 & 3
        target = ERROR_CHAT_ID if ERROR_CHAT_ID != 0 else MAIN_CHAT_ID
        _push(target, f"🚨 <b>[ALERT]</b> {msg}")
    else:
        # Mode 1 all to main
        _push(MAIN_CHAT_ID, f"🚨 <b>[ALERT]</b> {msg}")

def main(msg: str):
    """Direct to main channel (high visibility updates)."""
    if not should_send("main"): return
    _push(MAIN_CHAT_ID, msg)
