from . import worker
from . import logger
from . import router
from . import client

# M3TAL Telegram Service (v3 Layered System Orchestrator)
# Responsibility: Lifecycle management and public API exposure.

def start():
    """Wakes up the telegram subsystem."""
    worker.start()

def stop():
    """Graceful teardown."""
    worker.stop()

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
