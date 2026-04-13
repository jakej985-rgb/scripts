import os
import sys
import time
import signal
import threading
import subprocess
from pathlib import Path

# --- Path System Bootstrap ----------------------------------------------------
# We assume this script is run from control-plane/ as 'python run.py' 
# or from root as 'python -m control-plane.run'
CONTROL_PLANE = Path(__file__).resolve().parent
REPO_ROOT = CONTROL_PLANE.parent

# Ensure the control-plane and its agents are in sys.path
if str(CONTROL_PLANE) not in sys.path:
    sys.path.append(str(CONTROL_PLANE))
if str(CONTROL_PLANE / "agents") not in sys.path:
    sys.path.append(str(CONTROL_PLANE / "agents"))

from config.env import validate_env
from config.validate import validate
from utils.lock import acquire_global_lock, release_global_lock

# --- Signals ------------------------------------------------------------------
_shutdown_event = threading.Event()

def _handle_signal(signum, frame):
    print(f"\n[MASTER] Received signal {signum}. Shutting down M3TAL Control Plane...")
    _shutdown_event.set()

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)

# --- Network Check ------------------------------------------------------------
def ensure_proxy_network():
    """Ensure the 'proxy' network exists."""
    print("[MASTER] Checking 'proxy' network...")
    try:
        # Check if network exists
        subprocess.run(["docker", "network", "inspect", "proxy"], 
                       check=True, capture_output=True)
        print("  ✅ 'proxy' network found.")
    except subprocess.CalledProcessError:
        print("  ⚠️ 'proxy' network missing. Creating now...")
        try:
            subprocess.run(["docker", "network", "create", "proxy"], check=True)
            print("  ✅ 'proxy' network created successfully.")
        except subprocess.CalledProcessError as e:
            print(f"  ❌ FATAL: Failed to create 'proxy' network: {e}")
            sys.exit(1)

# --- Components ---------------------------------------------------------------
def start_supervisor():
    """Launch the agent supervisor as a child process."""
    print("[MASTER] Starting Agent Supervisor...")
    # We use the absolute path to agents/run.py
    supervisor_script = CONTROL_PLANE / "agents" / "run.py"
    
    # We pass the current environment
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(CONTROL_PLANE), str(CONTROL_PLANE / "agents"), env.get("PYTHONPATH", "")])
    
    # Run supervisor in a subprocess so it can manage its own signal handling
    return subprocess.Popen([sys.executable, str(supervisor_script)], env=env)

def start_bot():
    """Start the Telegram bot system (Worker + Listener) in a thread."""
    print("[MASTER] Starting Telegram Bot Runtime...")
    try:
        from agents.telegram.bot import run_bot
        t = threading.Thread(target=run_bot, name="TelegramBot", daemon=True)
        t.start()
        print("  ✅ Telegram Bot Runtime started.")
        return t
    except Exception as e:
        print(f"  ❌ Failed to start Telegram Bot: {e}")
        return None

# --- Main Entry ---------------------------------------------------------------
def main():
    print("=" * 40)
    print("📡 M3TAL CONTROL PLANE v2.0")
    print("=" * 40)
    
    # Audit Check: Soft CWD Warning
    if Path.cwd() != REPO_ROOT:
        print(f"⚠️  WARNING: Not running from repo root. (Current: {Path.cwd()})")
        print(f"   Recommended: Run from {REPO_ROOT} for deterministic pathing.")

    # 0. Global Lock
    if not acquire_global_lock():
        print("❌ FATAL: Another instance of M3TAL Control Plane is already running.")
        sys.exit(1)
        
    try:
        # Audit Check: Production Config Protection
        validate()

        # 1. Validate Env (Registry/Network)
        print("[M3TAL] Validating environment contract...")
        validate_env()
        print("[M3TAL] Env Loaded: OK")
        
        # 2. Ensure Network
        ensure_proxy_network()
        print("[M3TAL] Network: proxy (shared external)")
        
        # 3. Start Supervisor
        supervisor_proc = start_supervisor()
        
        # 4. Start Bot
        # Stagger startup: Supervisor first, then Bot
        time.sleep(2)
        bot_thread = start_bot()
        
        print("=" * 40)
        print("✅ M3TAL Control Plane is fully operational.")
        print("=" * 40)
        
        # 5. Keep alive and monitor
        while not _shutdown_event.is_set():
            if supervisor_proc.poll() is not None:
                print("🚨 [MASTER] Supervisor process exited unexpectedly!")
                break
            time.sleep(1)
            
        # 6. Shutdown
        print("[MASTER] Cleaning up...")
        if supervisor_proc.poll() is None:
            supervisor_proc.terminate()
            supervisor_proc.wait(timeout=5)
            
    finally:
        release_global_lock()
        print("[MASTER] Bye.")

if __name__ == "__main__":
    main()
