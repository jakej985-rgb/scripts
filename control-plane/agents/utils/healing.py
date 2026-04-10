import os
import sys
import time
import socket
import json
import tempfile
from pathlib import Path
from typing import Callable, Any, TypeVar

T = TypeVar('T')

# Root resolution
if "REPO_ROOT" not in globals():
    REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
    STATE_DIR = REPO_ROOT / "control-plane" / "state"
    LOCK_FILE = STATE_DIR / "healer.lock"

# Recovery Context
LOG_MODE = "file"  # Set to "stdout" if file writes fail globally

def retry(op: Callable[..., T], attempts: int = 3, delay: float = 0.5, backoff: float = 2.0) -> T:
    """Refined retry with exponential backoff and localized error classification."""
    current_delay = delay
    for i in range(attempts):
        try:
            return op()
        except Exception as e:
            if i == attempts - 1:
                raise
            
            msg = str(e).lower()
            # Simple keyword-based classifier
            retryable = any(x in msg for x in ["timeout", "busy", "connection", "unavailable", "network"])
            
            if not retryable and i == 0:
                # If not explicitly retryable but it's our first fail, we retry once anyway for weird IO
                pass
            elif not retryable:
                raise
            
            time.sleep(current_delay)
            current_delay *= backoff
    raise RuntimeError("Retry failed unexpectedly")

def is_writable(path: Path) -> bool:
    """Verifies both directory and file-level write access."""
    if not path.exists():
        return False
    
    test_file = path / f".write_test_{os.getpid()}"
    try:
        if path.is_dir():
            test_file.touch()
            test_file.unlink()
            return True
        return os.access(path, os.W_OK)
    except:
        return False

def atomic_write_json(path: Path, data: Any) -> bool:
    """Prevents corruption by writing to a temporary file then renaming."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use a temporary file in the same directory to ensure Atomic replace (os.replace)
        with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, suffix=".tmp", encoding="utf-8") as tmp:
            json.dump(data, tmp, indent=4)
            tmp.flush()
            os.fsync(tmp.fileno())
            temp_name = tmp.name
        
        os.replace(temp_name, str(path))
        return True
    except Exception as e:
        print(f"[HEALER] Atomic write failed for {path}: {e}")
        return False

def acquire_healer_lock(lock_timeout: int = 300) -> bool:
    """Acquires a stale-aware lock for healer/init coordination."""
    hostname = socket.gethostname()
    if LOCK_FILE.exists():
        try:
            # Check for stale lock
            age = time.time() - LOCK_FILE.stat().st_mtime
            if age > lock_timeout:
                print(f"[HEALER] Removing stale lock ({int(age)}s old)")
                LOCK_FILE.unlink(missing_ok=True)
            else:
                return False
        except:
            return False
            
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        # Lock identity: PID@Hostname
        LOCK_FILE.write_text(f"{os.getpid()}@{hostname}")
        return True
    except:
        return False

def release_healer_lock():
    """Cleanly removes the healer lock."""
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except:
        pass

def log_event(name: str, message: str):
    """Global logging aware of Log Mode (file vs stdout)."""
    global LOG_MODE
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"{ts} [{name.upper()}] {message}"
    
    if LOG_MODE == "file":
        try:
            log_dir = STATE_DIR / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{name}.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{formatted}\n")
            return
        except:
            LOG_MODE = "stdout"
            print(f"{ts} [HEALER_CORE] Falling back to stdout logging due to disk failure.")
    
    print(formatted)
