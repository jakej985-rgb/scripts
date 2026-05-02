import sys
import subprocess
import threading
import time
import re
import argparse
from datetime import datetime
from pathlib import Path

# M3TAL Docker Logs Agent (v2.4 Hardened + Clean Shutdown)
# Responsibility: Multi-stack log persistence with redaction and proactive alerting.

# Attempting catastrophic import of paths module
try:
    # Path bootstrap (V6.5.2)
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / ".env").exists() and (parent / "docker").exists():
            if str(parent / "control-plane") not in sys.path:
                sys.path.append(str(parent / "control-plane"))
            break
            
    from agents.utils.paths import DOCKER_DIR, CORE_LOGS_DIR, REPO_ROOT
    from agents.utils.guards import wrap_agent, SHUTDOWN_EVENT
except Exception as e:
    print(f"❌ FATAL: Critical path module missing or corrupted: {e}")
    sys.exit(1)

ROOT = REPO_ROOT
ENV_FILE = ROOT / ".env"

# --- Compose Command Detection ------------------------------------------------

def _detect_compose_cmd():
    """Detect available Docker Compose command variant.
    Returns a list like ['docker', 'compose'] or ['docker-compose'], or None.
    """
    # Try docker compose (plugin) first
    try:
        res = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True, text=True, timeout=10
        )
        if res.returncode == 0:
            return ["docker", "compose"]
    except Exception:
        pass

    # Try docker-compose (standalone v1)
    try:
        res = subprocess.run(
            ["docker-compose", "version"],
            capture_output=True, text=True, timeout=10
        )
        if res.returncode == 0:
            return ["docker-compose"]
    except Exception:
        pass

    return None

COMPOSE_CMD = _detect_compose_cmd()
if COMPOSE_CMD:
    print(f"🐳 [LOGGER] Compose detected: {' '.join(COMPOSE_CMD)}")
else:
    print("⚠️ [LOGGER] No Docker Compose available. Log streaming will be limited.")
SENSITIVE_KEYS = ["TOKEN", "SECRET", "KEY", "PASSWORD"]

# --- Alert Configuration -----------------------------------------------------
ALERT_PATTERNS = ["error", "critical", "exception", "traceback", "failed", "panic"]
SEVERITY_MAP = {
    "CRITICAL": ["panic", "fatal"],
    "ERROR": ["error", "failed", "exception", "traceback"],
    "WARNING": ["warn"],
}

ALERT_CACHE = {}
MAX_ALERT_CACHE = 1000
ALERT_COOLDOWN = 60  
MULTILINE_WINDOW = 2 
LAST_ALERT_TIME = 0.0

# Redefine SHUTDOWN_EVENT to use the one from guards
# SHUTDOWN_EVENT = threading.Event()

# --- Security: Redaction & Detection Engines ---------------------------------

def load_secrets():
    secrets = set()
    if not ENV_FILE.exists(): return []
    try:
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line: continue
                k, v = line.split("=", 1)
                if any(s in k.upper() for s in SENSITIVE_KEYS):
                    val = v.strip().strip('"').strip("'")
                    if val and len(val) > 4: secrets.add(val)
    except Exception as e:
        print(f"⚠️  Logging Security: Could not load secrets: {e}")
    return sorted(list(secrets), key=len, reverse=True)

def redact(line, secrets):
    if not secrets or not line: return line
    for secret in secrets:
        line = re.sub(re.escape(secret), "***REDACTED***", line, flags=re.IGNORECASE)
    return line

def normalize(msg: str) -> str:
    msg = msg.lower()
    msg = re.sub(r'\b[0-9a-f]{6,}\b', '<hex>', msg)
    msg = re.sub(r'\d+', '<num>', msg)
    return msg[:200]

def get_severity(line: str) -> str:
    l = line.lower()
    for level, keywords in SEVERITY_MAP.items():
        if any(k in l for k in keywords): return level
    return "INFO"

def should_alert(msg: str) -> bool:
    global LAST_ALERT_TIME, ALERT_CACHE
    now = time.time()
    if now - LAST_ALERT_TIME < MULTILINE_WINDOW: return False
    if len(ALERT_CACHE) > MAX_ALERT_CACHE: ALERT_CACHE.clear()
    key = normalize(msg)
    last_trigger = ALERT_CACHE.get(key, 0)
    if now - last_trigger > ALERT_COOLDOWN:
        ALERT_CACHE[key] = now
        LAST_ALERT_TIME = now
        return True
    return False

def send_alert(stack, severity, message):
    try:
        from agents import telegram
        if not telegram.is_available(): return
        formatted = f"[{severity}] {stack.upper()} ALERT\n{message[:3000]}"
        telegram.alert(formatted)
    except Exception as e:
        print(f"❌ [ALERT ERROR] {e}")

# --- Infrastructure: Discovery & Execution ------------------------------------

def discover_stacks():
    stacks = {}
    if not DOCKER_DIR.exists(): return stacks
    for path in DOCKER_DIR.iterdir():
        compose = path / "docker-compose.yml"
        if path.is_dir() and compose.exists():
            stacks[path.name] = compose
    return stacks

def stream_logs(stack_name, compose_file, secrets, alerts_enabled=False):
    """Streams logs with graceful SHUTDOWN_EVENT awareness."""
    if not COMPOSE_CMD:
        print(f"⚠️ [LOGGER] Skipping {stack_name} — no compose command available.")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_file = CORE_LOGS_DIR / f"{stack_name}_logs_{timestamp}.txt"
    CORE_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Build command using detected compose variant
    # --env-file is only needed for 'up'/'config', not 'logs'
    cmd = [*COMPOSE_CMD, "-f", str(compose_file), "logs", "-f", "--tail", "50"]
    
    print(f"🚀 [LOGGER] Streaming {stack_name} -> {log_file.name}")
    
    process = None
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )

            
            # Non-blocking read loop
            while not SHUTDOWN_EVENT.is_set():
                line = process.stdout.readline()
                if not line:
                    if process.poll() is not None: break
                    time.sleep(0.1)
                    continue
                
                safe_line = redact(line, secrets)
                if alerts_enabled and should_alert(safe_line):
                    send_alert(stack_name, get_severity(safe_line), safe_line)
                
                f.write(safe_line)
                f.flush()
                print(f"[{stack_name}] {safe_line}", end="")
                
    except Exception as e:
        if not SHUTDOWN_EVENT.is_set():
            print(f"❌ [LOGGER] Error in {stack_name}: {e}")
    finally:
        if process:
            # V6.5.2: Safe termination check
            if process.poll() is None:
                process.terminate()
            try: process.wait(timeout=2)
            except Exception: process.kill()

def agent_tick():
    """Wrapper for the agent tick, handles stack discovery and streaming."""
    if not COMPOSE_CMD:
        print("⚠ [LOGGER] No compose command available. Skipping log streaming.")
        return

    stacks = discover_stacks()
    if not stacks:
        print("⚠ [LOGGER] No stacks discovered.")
        return
        
    secrets = load_secrets()
    print(f"🔒 [SECURITY] Redaction active ({len(secrets)} secrets loaded)")
    
    # We always run 'all' when orchestrated
    threads = []
    for name, compose in stacks.items():
        t = threading.Thread(target=stream_logs, args=(name, compose, secrets, True), daemon=False)
        t.start()
        threads.append(t)

    # Monitor threads until shutdown or all finish
    last_health_update = 0
    while not SHUTDOWN_EVENT.is_set() and any(t.is_alive() for t in threads):
        time.sleep(1)
        # Heartbeat: keep health timestamp fresh so health_score doesn't
        # flag this agent as stalled (agent_tick never returns to wrap_agent)
        now = time.time()
        if now - last_health_update > 60:
            try:
                from agents.utils.guards import update_agent_health
                update_agent_health("docker_logs_agent", success=True)
            except Exception:
                pass
            last_health_update = now
        
    if not SHUTDOWN_EVENT.is_set() and not any(t.is_alive() for t in threads):
        # If all threads died but we didn't signal shutdown, something is wrong
        print("❌ [LOGGER] All log streams died unexpectedly.")
        sys.exit(1)

if __name__ == "__main__":
    wrap_agent("docker_logs_agent", agent_tick, interval=5)
