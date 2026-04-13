import queue

# M3TAL Telegram Queue System (v3 Layered)
# Responsibility: Thread-safe storage only. No execution logic.

_q = queue.Queue()

def enqueue(chat_id: int, message: str):
    """Ingestion point for all agents."""
    _q.put((chat_id, message))

def dequeue(timeout: int = 1):
    """Retrieval point for the worker."""
    try:
        return _q.get(timeout=timeout)
    except queue.Empty:
        return None

def task_done():
    """Mark task as complete."""
    _q.task_done()

def join():
    """Wait for all tasks to be processed."""
    _q.join()

def put_poison_pill():
    """Shut down signals."""
    _q.put(None)
