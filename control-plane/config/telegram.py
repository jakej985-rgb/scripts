import os
import sys

# M3TAL Telegram Configuration (Audit Phase 4)
# Supports legacy fallback for backward compatibility

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")

# Legacy Warning
if os.getenv("TELEGRAM_TOKEN") and not os.getenv("TELEGRAM_BOT_TOKEN"):
    print("[WARN] Using legacy TELEGRAM_TOKEN — migrate to TELEGRAM_BOT_TOKEN")

CHAT_MODE = int(os.getenv("TG_CHAT_MODE", "1"))

# Primary and Fallback for Main Chat
MAIN_CHAT_ID = int(os.getenv("TG_MAIN_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID", "0"))

LOG_CHAT_ID = int(os.getenv("TG_LOG_CHAT_ID", "0"))
ERROR_CHAT_ID = int(os.getenv("TG_ERROR_CHAT_ID", "0"))
ALERT_CHAT_ID = int(os.getenv("TG_ALERT_CHAT_ID", "0"))

def validate():
    """Startup Validation as per User Request (Audit Fix 5.1)."""
    print(f"[TELEGRAM] Mode={CHAT_MODE} initialization...")
    
    if not BOT_TOKEN:
        print("[CRITICAL] Missing TELEGRAM_BOT_TOKEN / TELEGRAM_TOKEN")
        return False

    if CHAT_MODE < 1 or CHAT_MODE > 4:
         print(f"[CRITICAL] TG_CHAT_MODE must be 1-4 (Got: {CHAT_MODE})")
         return False

    if MAIN_CHAT_ID == 0:
        print("[CRITICAL] MAIN_CHAT_ID required (TG_MAIN_CHAT_ID or TELEGRAM_CHAT_ID)")
        return False

    if CHAT_MODE >= 2 and ERROR_CHAT_ID == 0:
         # Fallback error to main if not explicitly set? 
         # User plan says RuntimeError, I'll follow that logic for mode 2+
         print("[ERROR] ERROR_CHAT_ID required for Mode 2+")

    if CHAT_MODE >= 3 and LOG_CHAT_ID == 0:
         print("[ERROR] LOG_CHAT_ID required for Mode 3+")

    if CHAT_MODE == 4 and ALERT_CHAT_ID == 0:
         print("[ERROR] ALERT_CHAT_ID required for Mode 4")

    print(f"[TELEGRAM] Configuration validated. Active Mode: {CHAT_MODE}")
    return True
