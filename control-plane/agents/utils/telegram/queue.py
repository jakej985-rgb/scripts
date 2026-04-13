import queue
import threading
from .router import send

# M3TAL Telegram Queue System (Audit Phase 4)
# Asynchronous non-blocking worker for telemetry delivery

import atexit

_q = queue.Queue()
MAX_LEN = 4000
_worker_thread = None

def worker():
    """Crash-proof background worker with poison pill support."""
    while True:
        item = _q.get()
        try:
            if item is None:  # Poison pill
                break
            chat_id, msg = item
            
            # Message Size Protection
            if len(msg) > MAX_LEN:
                msg = msg[:MAX_LEN] + "... [truncated]"
                
            send(chat_id, msg)
        except Exception as e:
            print(f"[TELEGRAM WORKER ERROR] {e}")
        finally:
            _q.task_done()

def _drain_on_exit():
    """Graceful shutdown: send poison pill and wait for queue to empty."""
    _q.put(None)
    _q.join()

def start_worker():
    """Initializes the background worker and registers exit handler."""
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return _worker_thread
        
    _worker_thread = threading.Thread(target=worker, daemon=True)
    _worker_thread.start()
    atexit.register(_drain_on_exit)
    return _worker_thread

def enqueue(chat_id: int, message: str):
    """Safe ingestion point for all agents."""
    _q.put((chat_id, message))
