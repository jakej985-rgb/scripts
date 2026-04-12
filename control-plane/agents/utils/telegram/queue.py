import queue
import threading
from .router import send

# M3TAL Telegram Queue System (Audit Phase 4)
# Asynchronous non-blocking worker for telemetry delivery

_q = queue.Queue()
MAX_LEN = 4000  # User Fix: Telegram limit protection (Audit Fix 5.3)

def worker():
    """Crash-proof background worker (Audit Fix 5.1)."""
    while True:
        try:
            chat_id, msg = _q.get()
            
            # Message Size Protection
            if len(msg) > MAX_LEN:
                msg = msg[:MAX_LEN] + "... [truncated]"
                
            send(chat_id, msg)
        except Exception as e:
            # User Fix: Catch all to prevent worker death (Audit Fix 5.1)
            print(f"[TELEGRAM WORKER ERROR] {e}")
        finally:
            _q.task_done()

def start_worker():
    """Initializes the daemonized worker thread."""
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t

def enqueue(chat_id: int, message: str):
    """Safe ingestion point for all agents."""
    _q.put((chat_id, message))
