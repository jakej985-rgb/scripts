import os
import sys
import time
import socket
from pathlib import Path

def get_lock_path() -> Path:
    """Return the path to the global control-plane lock file."""
    # We use a standard location in the state directory
    state_dir = Path(__file__).resolve().parent.parent / "state"
    locks_dir = state_dir / "locks"
    locks_dir.mkdir(parents=True, exist_ok=True)
    return locks_dir / "control_plane.lock"

def acquire_global_lock() -> bool:
    """
    Acquire a global lock for the control-plane.
    Prevents duplicate supervisors, bots, and race conditions.
    """
    lock_file = get_lock_path()
    pid = os.getpid()
    hostname = socket.gethostname()
    now = int(time.time())

    if lock_file.exists():
        try:
            content = lock_file.read_text().split(",")
            if len(content) >= 3:
                old_pid = int(content[0])
                old_hostname = content[2].strip()
                
                # If the PID is still running on the same host, we fail.
                # Note: On Windows, os.kill(pid, 0) works similarly to Unix.
                if old_hostname == hostname:
                    try:
                        os.kill(old_pid, 0)
                        print(f"❌ Global Lock active: PID {old_pid} on {old_hostname}")
                        return False
                    except (OSError, ProcessLookupError):
                        # PID is dead, safe to reclaim
                        print(f"⚠️ Reclaiming stale lock from dead PID {old_pid}")
                        pass
        except Exception as e:
            print(f"⚠️ Error reading existing lock: {e}")
            # If we can't read it, we assume it's corrupted and attempt to overwrite
            pass

    try:
        lock_file.write_text(f"{pid},{now},{hostname}")
        return True
    except Exception as e:
        print(f"❌ Failed to acquire global lock: {e}")
        return False

def release_global_lock():
    """Release the global control-plane lock."""
    lock_file = get_lock_path()
    if lock_file.exists():
        try:
            lock_file.unlink()
        except:
            pass

if __name__ == "__main__":
    if acquire_global_lock():
        print("Lock acquired. Press Enter to release...")
        input()
        release_global_lock()
    else:
        print("Failed to acquire lock.")
        exit(1)
