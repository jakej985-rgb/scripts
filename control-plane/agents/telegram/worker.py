import threading
import time
import atexit
from . import tg_queue
from . import client

# M3TAL Telegram Worker (v3 Layered)
# Responsibility: Background execution and rate limiting.

_worker_thread = None
_stop_event = threading.Event()

def _run():
    """Background loop processing the telegram queue."""
    while not _stop_event.is_set():
        item = tg_queue.dequeue(timeout=1)
        if item is None:
            continue
            
        chat_id, msg = item
        try:
            # RAW API Send
            success = client.send_text(chat_id, msg)
            
            if not success:
                # Basic retry logic or fallback logging could go here
                pass
                
            # Rate limiting / Backoff
            time.sleep(0.05) # 20 messages per second max (Telegram limit is roughly 30)
            
        except Exception as e:
            # Fallback to console if telegram is down
            print(f"[TELEGRAM WORKER CRASH] {e}")
        finally:
            tg_queue.task_done()

def start():
    """Starts the background worker thread."""
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
        
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_run, name="TelegramWorker", daemon=True)
    _worker_thread.start()
    
    # Register graceful shutdown
    atexit.register(stop)

def stop():
    """Shuts down the worker and drains the queue."""
    _stop_event.set()
    tg_queue.put_poison_pill()
    if _worker_thread:
        _worker_thread.join(timeout=5)
