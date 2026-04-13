from config.telegram import (
    CHAT_COUNT, MAIN_CHAT_ID, LOG_CHAT_ID, ERROR_CHAT_ID, 
    ALERT_CHAT_ID, ACTION_CHAT_ID, DOCKER_CHAT_ID
)
from .queue import enqueue

# M3TAL Telegram Dynamic Logger (v2 Hardened)
# Configurable 6-channel routing with mandatory truncation

MAX_LEN = 4000

def _truncate(msg: str) -> str:
    if len(msg) > MAX_LEN:
        return msg[:MAX_LEN] + "... [truncated]"
    return msg

def _push(chat_id: int, msg: str):
    if chat_id != 0:
        enqueue(chat_id, _truncate(msg))

def log(msg: str):
    """Normal operations routing (Channel 2)."""
    text = f"⚪ <b>[LOG]</b> {msg}"
    if CHAT_COUNT >= 3 and LOG_CHAT_ID != 0:
        _push(LOG_CHAT_ID, text)
    else:
        _push(MAIN_CHAT_ID, text)

def error(msg: str):
    """Failures routing (Channel 3)."""
    text = f"🔴 <b>[ERROR]</b> {msg}"
    if CHAT_COUNT >= 2:
        target = ERROR_CHAT_ID if ERROR_CHAT_ID != 0 else MAIN_CHAT_ID
        _push(target, text)
    else:
        _push(MAIN_CHAT_ID, text)

def alert(msg: str):
    """Critical issues routing (Channel 4)."""
    text = f"🚨 <b>[ALERT]</b> {msg}"
    if CHAT_COUNT >= 4 and ALERT_CHAT_ID != 0:
        _push(ALERT_CHAT_ID, text)
    elif CHAT_COUNT >= 2:
        target = ERROR_CHAT_ID if ERROR_CHAT_ID != 0 else MAIN_CHAT_ID
        _push(target, text)
    else:
        _push(MAIN_CHAT_ID, text)

def action(msg: str):
    """Command/Action routing (Channel 5)."""
    text = f"⚡ <b>[ACTION]</b> {msg}"
    if CHAT_COUNT >= 5 and ACTION_CHAT_ID != 0:
        _push(ACTION_CHAT_ID, text)
    else:
        _push(MAIN_CHAT_ID, text)

def docker(msg: str):
    """Infrastructure/Docker telemetry (Channel 6)."""
    text = f"🐳 <b>[DOCKER]</b> {msg}"
    if CHAT_COUNT == 6 and DOCKER_CHAT_ID != 0:
        _push(DOCKER_CHAT_ID, text)
    elif CHAT_COUNT >= 3 and LOG_CHAT_ID != 0:
        _push(LOG_CHAT_ID, text)
    else:
        _push(MAIN_CHAT_ID, text)

def send_main(msg: str):
    """Direct to main channel."""
    _push(MAIN_CHAT_ID, msg)
