import os
import sys
import subprocess
import threading
import time
import re
import argparse
from datetime import datetime
from pathlib import Path

# M3TAL Docker Logs Agent (v2.3 Hardened + Alerting)
# Responsibility: Multi-stack log persistence with redaction and proactive alerting.

# --- Root Resolution & Path Hardening (Phase 5) -------------------------------
def find_root():
    """Auto-detect repo root by walking up parents."""
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / ".env").exists() and (parent / "docker").exists():
            return parent
    return None

ROOT = find_root()
if not ROOT:
    print("❌ FATAL: Could not locate M3TAL repository root.")
    sys.exit(1)

# Ensure control-plane is in sys.path for agents.telegram import
sys.path.append(str(ROOT / "control-plane"))

try:
    from agents.utils.paths import DOCKER_DIR, CORE_LOGS_DIR
except ImportError:
    # Standalone fallback
    DOCKER_DIR = ROOT / "docker"
    CORE_LOGS_DIR = ROOT / "control-plane" / "state" / "logs"

ENV_FILE = ROOT / ".env"
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
ALERT_COOLDOWN = 60  # seconds
MULTILINE_WINDOW = 2  # seconds
LAST_ALERT_TIME = 0.0

# --- Security: Redaction & Detection Engines ---------------------------------

def load_secrets():
    """Hardened .env secrets loader."""
    secrets = set()
    if not ENV_FILE.exists():
        return []
    
    try:
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
                if "=" not in line: continue
                
                k, v = line.split("=", 1)
                if any(s in k.upper() for s in SENSITIVE_KEYS):
                    val = v.strip().strip('"').strip("'")
                    if val and len(val) > 4:
                        secrets.add(val)
    except Exception as e:
        print(f"⚠️  Logging Security: Could not load secrets for redaction: {e}")
        
    return sorted(list(secrets), key=len, reverse=True)

def redact(line, secrets):
    """Case-insensitive regex redaction pipe."""
    if not secrets or not line:
        return line
    
    for secret in secrets:
        pattern = re.escape(secret)
        line = re.sub(pattern, "***REDACTED***", line, flags=re.IGNORECASE)
    return line

def normalize(msg: str) -> str:
    """Hardens deduplication by masking dynamic numeric/hex values."""
    msg = msg.lower()
    # Mask hex hashes / IDs (6+ chars) FIRST
    msg = re.sub(r'\b[0-9a-f]{6,}\b', '<hex>', msg)
    # Mask numbers SECOND
    msg = re.sub(r'\d+', '<num>', msg)
    return msg[:200]

def get_severity(line: str) -> str:
    """Maps log content to severity levels."""
    l = line.lower()
    for level, keywords in SEVERITY_MAP.items():
        if any(k in l for k in keywords):
            return level
    return "INFO"

def should_alert(msg: str) -> bool:
    """Deduplication logic with multi-line suppression and memory safety."""
    global LAST_ALERT_TIME, ALERT_CACHE
    
    now = time.time()
    
    # 1. Multi-line suppression (Prevents spam from a single Traceback)
    if now - LAST_ALERT_TIME < MULTILINE_WINDOW:
        return False
        
    # 2. Memory safety cap
    if len(ALERT_CACHE) > MAX_ALERT_CACHE:
        ALERT_CACHE.clear()
        
    # 3. Deduplication via normalization
    key = normalize(msg)
    last_trigger = ALERT_CACHE.get(key, 0)
    
    if now - last_trigger > ALERT_COOLDOWN:
        ALERT_CACHE[key] = now
        LAST_ALERT_TIME = now
        return True
        
    return False

def send_alert(stack, severity, message):
    """Dispatches redacted notification to Telegram."""
    try:
        # Lazy import to ensure subsystem is ready
        from agents import telegram
        if not telegram.is_available():
            return
            
        formatted = f"[{severity}] {stack.upper()} ALERT\n{message[:3000]}"
        telegram.alert(formatted)
    except Exception as e:
        print(f"❌ [ALERT ERROR] {e}")

# --- Infrastructure: Discovery & Execution ------------------------------------

def discover_stacks():
    """Auto-scan /docker directory for compose projects."""
    stacks = {}
    if not DOCKER_DIR.exists():
        return stacks
    
    for path in DOCKER_DIR.iterdir():
        compose = path / "docker-compose.yml"
        if path.is_dir() and compose.exists():
            stacks[path.name] = compose
    return stacks

def stream_logs(stack_name, compose_file, secrets, alerts_enabled=False):
    """Streams logs from a specific stack to console and disk with redaction & alerting."""
    CORE_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_file = CORE_LOGS_DIR / f"{stack_name}_logs_{timestamp}.txt"
    
    cmd = [
        "docker", "compose",
        "--env-file", str(ENV_FILE),
        "-f", str(compose_file),
        "logs", "-f", "--tail", "100"
    ]
    
    print(f"🚀 [LOGGER] Streaming {stack_name} -> {log_file.name} {'(Alerts Active)' if alerts_enabled else ''}")
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                shell=(os.name == "nt")
            )
            
            for line in process.stdout:
                safe_line = redact(line, secrets)
                
                # Proactive Alerting Trigger
                if alerts_enabled:
                    l_lower = safe_line.lower()
                    if any(p in l_lower for p in ALERT_PATTERNS):
                        if should_alert(safe_line):
                            severity = get_severity(safe_line)
                            send_alert(stack_name, severity, safe_line)
                
                f.write(safe_line)
                f.flush()
                print(f"[{stack_name}] {safe_line}", end="")
                
    except Exception as e:
        print(f"❌ [LOGGER] Error in {stack_name} stream: {e}")

# --- CLI Dispatcher -----------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="M3TAL Docker Logs Agent")
    parser.add_argument("stack", nargs="?", default="all", help="Stack name or 'all'")
    parser.add_argument("--alerts", action="store_true", help="Enable proactive Telegram alerting")
    args = parser.parse_args()
    
    target = args.stack.lower()
    
    stacks = discover_stacks()
    if not stacks:
        print(f"❌ ERROR: No Docker projects found in {DOCKER_DIR}")
        sys.exit(1)
        
    secrets = load_secrets()
    print(f"🔒 [SECURITY] Redaction active ({len(secrets)} secrets loaded)")
    
    if target == "all":
        print(f"📡 [LOGGER] Monitoring all stacks: {', '.join(stacks.keys())}")
        threads = []
        for name, compose in stacks.items():
            t = threading.Thread(
                target=stream_logs, 
                args=(name, compose, secrets, args.alerts), 
                name=f"Logger-{name}", 
                daemon=True
            )
            t.start()
            threads.append(t)
            
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 [LOGGER] Stopping log streams...")
    else:
        if target not in stacks:
            print(f"❌ ERROR: Stack '{target}' not found.")
            sys.exit(1)
        
        try:
            stream_logs(target, stacks[target], secrets, args.alerts)
        except KeyboardInterrupt:
            print("\n🛑 [LOGGER] Stopped.")

if __name__ == "__main__":
    main()
