import sys
import os
import time
import signal
import random
import errno
from typing import Callable, Any

# Root addition for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR, LEADER_TXT, TIERS, validate_contract
from utils.identity import is_local_host, get_local_identity
from utils.state import save_json, load_json
from utils.logger import get_logger

logger = get_logger("guards")
HEALTH_SUBDIR = STATE_DIR / "health"
LOCK_SUBDIR = STATE_DIR / "locks"

# --- Lifecycle Globals --------------------------------------------------------
_SHUTDOWN_SIGNALED = False

def handle_signal(signum, _frame):
    global _SHUTDOWN_SIGNALED
    logger.info(f"Received signal {signum}. Requesting graceful shutdown...")
    _SHUTDOWN_SIGNALED = True

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

# --- System Modes -------------------------------------------------------------
# HEALTHY: Normal operation
# DEGRADED: One or more agents failing/missing contracts
# LOCKED: Manual lock-down, no restarts or critical ticks (future)
SYSTEM_MODE_FILE = os.path.join(STATE_DIR, "system_mode.json")

def set_system_mode(mode: str):
    save_json(SYSTEM_MODE_FILE, {"mode": mode, "updated_at": int(time.time())}, caller="run")

def get_system_mode() -> str:
    data = load_json(SYSTEM_MODE_FILE, default={"mode": "HEALTHY"})
    return data.get("mode", "HEALTHY")

# --- Process Infrastructure ---------------------------------------------------

def is_pid_running(pid: int) -> bool:
    """Production-grade PID check (cross-platform)."""
    if pid <= 0: return False
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        try:
            os.kill(pid, 0)
            return True
        except OSError as e:
            # ESRCH (No such process) means dead.
            # EPERM/EACCES (Permission denied) means alive but restricted.
            return e.errno in (errno.EPERM, errno.EACCES)
        except Exception:
            return False


def is_leader():
    if not os.path.exists(LEADER_TXT):
        return True
    try:
        with open(LEADER_TXT, 'r') as f:
            leader_name = f.read().strip()
        return is_local_host(leader_name)
    except Exception:
        return True

# --- Hardened Locking (V4) ----------------------------------------------------

def acquire_lock(agent_name: str, ttl_seconds: int = 300) -> bool:
    """Format: pid,timestamp,hostname,process_name
    Rules (V4): Reclaim only if (PID dead AND TTL expired).
    """
    os.makedirs(LOCK_SUBDIR, exist_ok=True)
    lock_file = os.path.join(LOCK_SUBDIR, f"{agent_name}.pid")
    pid = os.getpid()
    host = get_local_identity()
    proc_name = os.path.basename(sys.argv[0])
    now = int(time.time())

    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as f:
                content = f.read().strip().split(",")
                
            if len(content) >= 4:
                old_pid, old_ts, old_host, old_proc = content[0:4]
                old_pid, old_ts = int(old_pid), int(old_ts)
                
                # RECLAIM RULES (V4 Final)
                # We only reclaim if PID is dead AND TTL (>300s) has passed.
                # process_name and host are for debugging/cross-container validation.
                alive = is_pid_running(old_pid)
                expired = (now - old_ts) > ttl_seconds
                
                # SELF-RECLAIM: If same PID and same Host, it's safe to overwrite (Audit fix 4.10)
                if old_pid == pid and old_host == host:
                    logger.info(f"Self-lock detected for {agent_name} (PID {pid}). Reclaiming.")
                elif alive:
                    logger.warning(f"Lock conflict for {agent_name}: PID {old_pid} on {old_host} is still alive.")
                    return False
                elif not expired:
                    logger.warning(f"Lock for {agent_name} is stale but TTL not met ({now - old_ts}s < {ttl_seconds}s).")
                    return False
                else:
                    logger.info(f"Reclaiming stale lock for {agent_name} (Dead PID {old_pid}, Expired TTL).")
            
            os.remove(lock_file)
        except Exception as e:
            logger.error(f"Error checking lock for {agent_name}: {e}")
            try: os.remove(lock_file)
            except Exception: pass

    try:
        with open(lock_file, 'w') as f:
            f.write(f"{pid},{now},{host},{proc_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to write lock for {agent_name}: {e}")
        return False

def heartbeat_lock(agent_name: str):
    """V4 Update: Rewrite the entire lock line to update the timestamp."""
    lock_file = os.path.join(LOCK_SUBDIR, f"{agent_name}.pid")
    if os.path.exists(lock_file):
        try:
            # We just overwrite with current state to keep it atomic and fresh
            acquire_lock(agent_name)
        except Exception:
            pass

def release_lock(agent_name: str):
    lock_file = os.path.join(LOCK_SUBDIR, f"{agent_name}.pid")
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
        except Exception:
            pass

# --- Health & Execution -------------------------------------------------------

def update_agent_health(agent_name: str, success: bool, error_msg: str = None):
    os.makedirs(HEALTH_SUBDIR, exist_ok=True)
    path = os.path.join(HEALTH_SUBDIR, f"{agent_name}.json")
    now = int(time.time())
    
    stats = {
        "last_success": now if success else 0,
        "last_failure": now if not success else 0,
        "status": "healthy" if success else "failing",
        "error": error_msg,
        "timestamp": now,
        "shutdown": _SHUTDOWN_SIGNALED,
        "mode": get_system_mode()
    }
    save_json(path, stats, caller=agent_name)

def wrap_agent(agent_name: str, func: Callable[[], Any], interval: int = 10):
    """Production Agent Wrapper.
    Safety: Contract check -> Lock acquisition -> Jittered Loop -> Tier Health.
    """
    agent_logger = get_logger(agent_name)
    bypass = os.getenv("M3TAL_BYPASS_ORCHESTRATOR") == "1"
    
    pid = os.getpid()
    host = get_local_identity()
    
    # Standardized Identity Log
    agent_logger.info(f"[DEBUG] AGENT={agent_name} PID={pid} HOST={host} BYPASS={bypass}")
    
    if bypass:
        print(f"⚠️  WARNING: Agent {agent_name} running outside orchestrator — no lifecycle guarantees.")

    # 1. Contract Pre-check (V4)
    success, err = validate_contract(agent_name)
    tier = TIERS.get(agent_name, 2)
    
    if not success:
        if tier == 1:
            agent_logger.error(f"FATAL: {err}")
            sys.exit(1)
        else:
            agent_logger.warning(f"DEGRADED: {err}")
            update_agent_health(agent_name, success=False, error_msg=err)

    # 2. Lock Acquisition
    if not acquire_lock(agent_name):
        agent_logger.warning(f"Agent {agent_name} already running (lock conflict). Exiting.")
        sys.exit(0)

    try:
        agent_logger.info(f"--- Agent {agent_name} Persistent Loop Started ---")
        
        while not _SHUTDOWN_SIGNALED:
            # 3. Tier Health Check (Tier 2 requires its contract state)
            if tier == 2:
                # Audit Fix: Wait for specific contract files, not just a single shared sentinel (H9)
                success, err = validate_contract(agent_name)
                if not success:
                    agent_logger.warning(f"Waiting for dependencies: {err}")
                    time.sleep(interval)
                    continue

            if not is_leader():
                time.sleep(interval)
                heartbeat_lock(agent_name)
                continue

            try:
                func()
                update_agent_health(agent_name, success=True)
            except Exception as e:
                # Error classification (V3)
                err_type = "TRANSIENT"
                if isinstance(e, (ImportError, NameError, SyntaxError)):
                    err_type = "CODE"
                elif isinstance(e, (FileNotFoundError, KeyError)) and tier == 1:
                    err_type = "CONFIG"
                
                agent_logger.error(f"Agent {agent_name} tick failed ({err_type}): {e}", exc_info=True)
                update_agent_health(agent_name, success=False, error_msg=f"{err_type}: {e}")
                
                if err_type in ["CODE", "CONFIG"] and tier == 1:
                    agent_logger.critical(f"FATAL {err_type} error in Tier 1 agent. Shutting down.")
                    sys.exit(1)

            heartbeat_lock(agent_name)

            # 4. Sleep with Jitter (V4)
            jitter = random.uniform(0, 5)
            sleep_time = interval + jitter
            for _ in range(int(sleep_time)):
                if _SHUTDOWN_SIGNALED:
                    break
                time.sleep(1)

        agent_logger.info(f"--- Agent {agent_name} Shutdown Cleanly ---")
    finally:
        release_lock(agent_name)
