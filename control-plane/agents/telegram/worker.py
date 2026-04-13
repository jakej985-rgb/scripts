"""
M3TAL Telegram Worker (v3.2 Hardened)
Responsibility: Background execution, circuit breaker, clean shutdown.
"""

import sys
import threading
import time

from . import tg_queue
from . import client

# --- State -------------------------------------------------------------------
_worker_thread: threading.Thread | None = None
_stop_event   = threading.Event()
_start_lock   = threading.Lock()

# --- Circuit Breaker thresholds ----------------------------------------------
CB_OPEN_THRESHOLD  = 5    # consecutive failures before opening
CB_RESET_AFTER     = 60   # seconds to wait before resetting
STATS_INTERVAL     = 300  # seconds between stats reports


# --- Worker Loop -------------------------------------------------------------

def _run() -> None:
    """
    Self-healing background loop.

    Design:
    - Items are dequeued with a 1-second timeout so the loop can react to
      _stop_event without blocking forever.
    - task_done() is only called when an item was actually dequeued, never on
      timeout (None return), preventing ValueError from queue.join().
    - Circuit breaker: after CB_OPEN_THRESHOLD consecutive send failures the
      loop pauses CB_RESET_AFTER seconds to avoid hammering a dead API.
    - All exceptions inside the processing block are caught individually so
      one bad message cannot kill the worker thread.
    """
    print("[TELEGRAM] Worker started.")
    consecutive_failures = 0
    circuit_open         = False
    circuit_opened_at    = 0.0
    last_stats_time      = time.time()

    while not _stop_event.is_set():

        # ── Periodic stats report ─────────────────────────────────────────────
        now = time.time()
        if now - last_stats_time >= STATS_INTERVAL:
            try:
                s = client.get_stats()
                print(
                    f"[TELEGRAM STATS] sent={s['sent']} failed={s['failed']} "
                    f"retries={s['retries']} queue={tg_queue.size()} "
                    f"last_error={s['last_error']}",
                )
            except Exception as exc:
                print(f"[TELEGRAM] Stats report failed: {exc}", file=sys.stderr)
            last_stats_time = now

        # ── Circuit Breaker ───────────────────────────────────────────────────
        if circuit_open:
            elapsed = time.time() - circuit_opened_at
            if elapsed < CB_RESET_AFTER:
                time.sleep(1)
                continue
            else:
                print(
                    f"[TELEGRAM] Circuit breaker reset after {elapsed:.0f}s.",
                )
                circuit_open         = False
                consecutive_failures = 0

        # ── Dequeue (non-blocking timeout) ────────────────────────────────────
        item = tg_queue.dequeue(timeout=1)
        if item is None:
            # Queue was empty — do NOT call task_done(), nothing was taken
            continue

        # ── Process item ──────────────────────────────────────────────────────
        # At this point, task_done() MUST be called in a finally block.
        try:
            chat_id, msg = item

            if not isinstance(chat_id, int) or chat_id == 0:
                print(
                    f"[TELEGRAM WORKER] Dropping message with invalid chat_id: "
                    f"{repr(chat_id)}",
                    file=sys.stderr,
                )
                consecutive_failures = max(0, consecutive_failures - 1)
                continue 

            success = client.send_text(chat_id, msg)

            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                last_err = client.get_stats().get("last_error", "unknown")
                print(
                    f"[TELEGRAM WORKER] Send failed (failures={consecutive_failures}): "
                    f"{last_err}",
                    file=sys.stderr,
                )
                if consecutive_failures >= CB_OPEN_THRESHOLD:
                    circuit_open       = True
                    circuit_opened_at  = time.time()
                    print(
                        f"[TELEGRAM] Circuit breaker OPEN after "
                        f"{consecutive_failures} consecutive failures. "
                        f"Pausing {CB_RESET_AFTER}s.",
                        file=sys.stderr,
                    )

            # Telegram global rate limit: max ~30 messages/second per bot.
            # 50ms between sends keeps us well under that ceiling.
            time.sleep(0.05)

        except ValueError as exc:
            # item was not a (chat_id, msg) tuple — corrupted enqueue
            print(
                f"[TELEGRAM WORKER] Malformed queue item {repr(item)}: {exc}",
                file=sys.stderr,
            )
            consecutive_failures += 1

        except Exception as exc:
            # Catch-all — log and continue so the thread never dies
            consecutive_failures += 1
            print(
                f"[TELEGRAM WORKER] Unexpected error processing message: {exc}",
                file=sys.stderr,
            )
            time.sleep(1)

        finally:
            # Audit Fix: task_done() must be called for EVERY successful dequeue.
            # The 'continue' above for empty queue skips this block.
            try:
                tg_queue.task_done()
            except ValueError:
                pass

    print("[TELEGRAM] Worker loop exited cleanly.")


# --- Lifecycle ---------------------------------------------------------------

def start() -> None:
    """Starts the background worker thread. Idempotent — safe to call twice."""
    global _worker_thread

    with _start_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return  # Already running

        _stop_event.clear()
        _worker_thread = threading.Thread(
            target=_run,
            name="TelegramWorker",
            daemon=True,
        )
        _worker_thread.start()
        print("[TELEGRAM] Worker thread started.")


def stop(timeout: int = 5) -> None:
    """
    Gracefully shuts down the worker.
    Signals stop, sends a poison pill so the dequeue() unblocks immediately,
    then waits up to `timeout` seconds for the thread to exit.
    """
    _stop_event.set()
    tg_queue.put_poison_pill()

    if _worker_thread is not None:
        _worker_thread.join(timeout=timeout)
        if _worker_thread.is_alive():
            print(
                f"[TELEGRAM] WARNING: Worker did not stop within {timeout}s.",
                file=sys.stderr,
            )
        else:
            print("[TELEGRAM] Worker shut down cleanly.")


def is_running() -> bool:
    """Returns True if the worker thread is alive."""
    return _worker_thread is not None and _worker_thread.is_alive()
