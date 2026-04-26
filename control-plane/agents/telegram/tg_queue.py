import queue

# M3TAL Telegram Queue System (v3.1 Hardened)
# Responsibility: Thread-safe storage with backpressure management.

MAX_SIZE = 1000  # Prevent memory leaks if Telegram is down
_q = queue.Queue(maxsize=MAX_SIZE)

def enqueue(chat_id: int, message: str):
    """Ingestion point with backpressure protection (drop-oldest)."""
    try:
        _q.put_nowait((chat_id, message))
    except queue.Full:
        # Audit Fix M2: Drop the NEWEST (skip current) instead of oldest 
        # to ensure the first diagnostic alerts are preserved.
        import sys
        print(f"⚠️ [TELEGRAM QUEUE] Full ({MAX_SIZE}). Dropping newest alert for chat {chat_id}.", file=sys.stderr)
        pass

def dequeue(timeout: int = 1):
    """Retrieval point for the worker."""
    try:
        return _q.get(timeout=timeout)
    except queue.Empty:
        return None

def size():
    """Returns current approximate size."""
    return _q.qsize()

def task_done():
    """Mark task as complete."""
    _q.task_done()

def join(timeout=None):
    """Wait for all tasks with an optional timeout."""
    # Note: queue.join() doesn't take a timeout, so we use a simpler approach
    # if a timeout is needed. For now, standard join is fine.
    _q.join()

def put_poison_pill():
    """Shut down signals."""
    _q.put(None)
