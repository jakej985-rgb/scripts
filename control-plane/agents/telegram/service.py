import atexit
from . import worker
from . import logger
from config.telegram import BOT_TOKEN

# M3TAL Telegram Service (v3.1 Hardened Orchestrator)
# Responsibility: Lifecycle management and public API exposure.

_atexit_registered = False

def start():
    """Wakes up the telegram subsystem with connection validation."""
    global _atexit_registered
    
    if not BOT_TOKEN:
        print("🚨 [TELEGRAM] FATAL: BOT_TOKEN is missing or could not be loaded from .env")
        return

    # Connection Test (Audit Fix: Silent failure check)
    from . import client
    me = client.get_me()
    if me.get("ok"):
        bot_name = me.get("result", {}).get("username", "UnknownBot")
        print(f"✅ [TELEGRAM] Connected as @{bot_name}")
    else:
        print(f"⚠ [TELEGRAM] Connection test failed: {me.get('description', 'Unknown Error')}")
        
    worker.start()
    
    # Register shutdown globally (Audit Fix: Single registration guard)
    if not _atexit_registered:
        atexit.register(stop)
        _atexit_registered = True

def stop():
    """Graceful teardown with safety timeout."""
    worker.stop(timeout=5)

def send_main(msg: str):
    """Direct-to-main override."""
    from config.telegram import MAIN_CHAT_ID
    from . import tg_queue
    tg_queue.enqueue(MAIN_CHAT_ID, msg)

def send_direct(chat_id: int, msg: str):
    """Direct-to-chat override for specific user responses."""
    from . import tg_queue
    tg_queue.enqueue(chat_id, msg)

# Expose standard logging API for convenience
log = logger.log
error = logger.error
alert = logger.alert
action = logger.action
docker = logger.docker
