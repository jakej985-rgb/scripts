import threading
import time
import atexit
from . import tg_queue
from . import client

# M3TAL Telegram Worker (v3.1 Hardened)
# Responsibility: Background execution, rate limiting, and self-healing.

_worker_thread = None
_stop_event = threading.Event()
_start_lock = threading.Lock()

def _run():
    """Self-healing background loop with Circuit Breaker and Stats reporting."""
    print("[TELEGRAM] Worker started.")
    consecutive_failures = 0
    last_stats_time = time.time()
    
    while not _stop_event.is_set():
        try:
            # Stats Reporting (Every 5 minutes if active)
            if time.time() - last_stats_time > 300:
                s = client.get_stats()
                print(f"[TELEGRAM STATS] sent={s['sent']} failed={s['failed']} retry={s['retries']} q={tg_queue.size()}")
                last_stats_time = time.time()

            # Soft Circuit Breaker
            if consecutive_failures >= 5:
                print(f"[TELEGRAM] Circuit Breaker ACTIVE. Pausing for 60s...")
                time.sleep(60)
                consecutive_failures = 0
                continue

            item = tg_queue.dequeue(timeout=1)
            if item is None:
                continue
                
            chat_id, msg = item
            
            # RAW API Send
            success = client.send_text(chat_id, msg)
            
            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
            
            # Global Rate Limiting (Sanity check)
            time.sleep(0.05) 
            
        except Exception as e:
            consecutive_failures += 1
            # Critical: Log to console only to avoid recursive loops
            print(f"[TELEGRAM WORKER LOOP ERROR] {e}")
            time.sleep(1) # cool down
            
        finally:
            try: tg_queue.task_done()
            except: pass

def start():
    """Starts the background worker thread (Idempotent)."""
    global _worker_thread
    with _start_lock:
        if _worker_thread and _worker_thread.is_alive():
            return
            
        _stop_event.clear()
        _worker_thread = threading.Thread(target=_run, name="TelegramWorker", daemon=True)
        _worker_thread.start()
        
        # Register graceful shutdown
        # atexit.register(stop)  <- Moved to service.py for manual control if needed

def stop(timeout: int = 5):
    """Shuts down the worker and drains the queue with a hard timeout."""
    _stop_event.set()
    tg_queue.put_poison_pill()
    if _worker_thread:
        _worker_thread.join(timeout=timeout)
    print("[TELEGRAM] Worker shut down.")
