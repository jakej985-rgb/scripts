import os
import sys
import time
import socket
import json
import tempfile
import errno
from pathlib import Path
from typing import Callable, Any, TypeVar, Optional

T = TypeVar('T')

from .paths import REPO_ROOT, STATE_DIR, LOCK_DIR

LOCK_FILE = LOCK_DIR / "healer.lock"

# Recovery Context
LOG_MODE = "file"  # Set to "stdout" if file writes fail globally

def is_pid_running(pid: int) -> bool:
    """Cross-platform check for PID existence."""
    if pid <= 0: return False
    
    # Windows Implementation
    if os.name == 'nt':
        try:
            # os.kill(pid, 0) is supported on Windows for existence check
            os.kill(pid, 0)
            return True
        except OSError as e:
            return e.errno == errno.EPERM # EPERM means it exists but we can't kill it (still alive)
        except Exception:
            return False
    
    # Unix Implementation
    else:
        try:
            os.kill(pid, 0)
        except OSError as err:
            if err.errno == errno.ESRCH:
                return False
            elif err.errno == errno.EPERM:
                return True
            else:
                raise
        else:
            return True

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
            retryable = any(x in msg for x in ["timeout", "busy", "connection", "unavailable", "network"])
            
            if not retryable and i == 0:
                pass
            elif not retryable:
                raise
            
            time.sleep(current_delay)
            current_delay *= backoff
    raise RuntimeError("Retry failed unexpectedly")

def is_writable(path: Path) -> bool:
    if not path.exists(): return False
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
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
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
            content = LOCK_FILE.read_text().split('@')
            lock_pid = int(content[0])
            lock_host = content[1] if len(content) > 1 else ""
            
            # 1. Local Stale Check (PID Based)
            if lock_host == hostname:
                if not is_pid_running(lock_pid):
                    print(f"[HEALER] Removing stale local lock (PID {lock_pid} is dead)")
                    LOCK_FILE.unlink(missing_ok=True)
                else:
                    return False
            # 2. Remote Stale Check (Time Based)
            else:
                age = time.time() - LOCK_FILE.stat().st_mtime
                if age > lock_timeout:
                    print(f"[HEALER] Removing stale remote lock ({int(age)}s old)")
                    LOCK_FILE.unlink(missing_ok=True)
                else:
                    return False
        except Exception:
            # If we can't parse it, check age
            try:
                if time.time() - LOCK_FILE.stat().st_mtime > 10: # Safety buffer
                     LOCK_FILE.unlink(missing_ok=True)
                else:
                    return False
            except:
                return False
            
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        LOCK_FILE.write_text(f"{os.getpid()}@{hostname}")
        return True
    except:
        return False

def release_healer_lock():
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except:
        pass

def log_event(name: str, message: str, symbol: Optional[str] = None):
    global LOG_MODE
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    sym_prefix = f"{symbol} " if symbol else ""
    formatted = f"{ts} {sym_prefix}[{name.upper()}] {message}"
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
            print(f"{ts} [HEALER_CORE] Falling back to stdout.")
    print(formatted)
