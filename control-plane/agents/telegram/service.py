import atexit
from . import worker
from . import logger
from config.telegram import BOT_TOKEN

# M3TAL Telegram Service (v3.1 Hardened Orchestrator)
# Responsibility: Lifecycle management and public API exposure.

def start():
    """Wakes up the telegram subsystem with fail-fast validation."""
    if not BOT_TOKEN:
        print("🚨 [TELEGRAM] FATAL: BOT_TOKEN is missing. Subsystem will not start.")
        return
        
    worker.start()
    
    # Register shutdown globally
    atexit.register(stop)

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
