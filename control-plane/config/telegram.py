import os

# M3TAL Telegram Configuration (Audit Phase 4 - Upgraded to 6-Channel v2)
# Supports legacy fallback for backward compatibility

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")

# NEW: Transition to CHAT_COUNT (1-6)
CHAT_COUNT = int(os.getenv("TG_CHAT_COUNT", os.getenv("TG_CHAT_MODE", "1")))

# Primary and Fallback for Main Chat
MAIN_CHAT_ID = int(os.getenv("TG_MAIN_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID", "0"))

LOG_CHAT_ID = int(os.getenv("TG_LOG_CHAT_ID", "0"))
ERROR_CHAT_ID = int(os.getenv("TG_ERROR_CHAT_ID", "0"))
ALERT_CHAT_ID = int(os.getenv("TG_ALERT_CHAT_ID", "0"))

# NEW: Channel 5 & 6
ACTION_CHAT_ID = int(os.getenv("TG_ACTION_CHAT_ID", "0"))
DOCKER_CHAT_ID = int(os.getenv("TG_DOCKER_CHAT_ID", "0"))

# NEW: Security Whitelist
_allowed_raw = os.getenv("ALLOWED_USERS", "0")
ALLOWED_USERS = [
    int(x.strip()) for x in _allowed_raw.split(",") 
    if x.strip().isdigit() and int(x.strip()) > 0
]

def is_allowed_user(user_id: int) -> bool:
    """Security check for remote commands."""
    return user_id in ALLOWED_USERS

def validate():
    """Startup Validation for the 6-channel Control Plane."""
    print(f"[TELEGRAM] Mode={CHAT_COUNT}-channel initialization...")
    
    if not BOT_TOKEN:
        print("[CRITICAL] Missing TELEGRAM_BOT_TOKEN")
        return False

    if CHAT_COUNT < 1 or CHAT_COUNT > 6:
         print(f"[CRITICAL] TG_CHAT_COUNT must be 1-6 (Got: {CHAT_COUNT})")
         return False

    if MAIN_CHAT_ID == 0:
        print("[CRITICAL] MAIN_CHAT_ID required")
        return False

    # Validation requirements per count
    if CHAT_COUNT >= 2 and ERROR_CHAT_ID == 0:
         print("[ERROR] ERROR_CHAT_ID required for Mode 2+")

    if CHAT_COUNT >= 3 and LOG_CHAT_ID == 0:
         print("[ERROR] LOG_CHAT_ID required for Mode 3+")

    if CHAT_COUNT >= 4 and ALERT_CHAT_ID == 0:
         print("[ERROR] ALERT_CHAT_ID required for Mode 4+")

    if CHAT_COUNT >= 5 and ACTION_CHAT_ID == 0:
         print("[ERROR] ACTION_CHAT_ID required for Mode 5+")

    if CHAT_COUNT == 6 and DOCKER_CHAT_ID == 0:
         print("[ERROR] DOCKER_CHAT_ID required for Mode 6")

    print(f"[TELEGRAM] Configuration validated. Allowed Users: {len(ALLOWED_USERS)}")
    return True
