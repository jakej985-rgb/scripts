import sys
import os
import subprocess
import argparse
from pathlib import Path

# M3TAL Unified CLI (v2.2 Production-Grade)
# Responsibility: Centralized entrypoint for all M3TAL orchestration and observability.

def find_root():
    """Auto-detect repo root by walking up parents until .env + docker/ are found."""
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / ".env").exists() and (parent / "docker").exists():
            return parent
    return None

# Attempting catastrophic import of paths module
try:
    _root = find_root()
    if not _root: raise RuntimeError("Repo root not found")
    sys.path.append(str(_root / "control-plane"))
    from agents.utils.paths import (
        REPO_ROOT, SCRIPTS_DIR, AGENTS_DIR, CONTROL_PLANE
    )
except Exception as e:
    print(f"[X] FATAL: Critical path module missing or corrupted: {e}")
    sys.exit(1)

ROOT = REPO_ROOT

# --- Execution Helpers --------------------------------------------------------
def run_script(path, *args, check=False):
    """Executes an internal script while passing repo-root context."""
    if not path.exists():
        print(f"[X] Error: Script not found at {path}")
        return
    
    cmd = [sys.executable, str(path)] + list(args)
    try:
        # We don't use 'check=True' for long-running agents so they can be 
        # interrupted with Ctrl+C without showing a traceback.
        cp = subprocess.run(cmd, check=check)
        return cp.returncode
    except KeyboardInterrupt:
        print("\n[!] Operation cancelled by user.")
        return 1
    except Exception as e:
        print(f"[X] Execution error: {e}")
        return 1

# --- Command Handlers ---------------------------------------------------------
def cmd_logs(args):
    """Starts the Docker logs agent."""
    path = AGENTS_DIR / "docker_logs_agent.py"
    # Forward arguments
    args_list = [args.stack]
    if args.alerts:
        args_list.append("--alerts")
    return run_script(path, *args_list)

def cmd_env():
    """Launches the environment audit tool."""
    path = SCRIPTS_DIR / "view_env.py"
    return run_script(path)

def cmd_audit(args):
    """Runs the infrastructure contract auditor."""
    path = CONTROL_PLANE / "config" / "audit.py"
    args_list = []
    if hasattr(args, 'json') and args.json:
        args_list.append("--json")
    return run_script(path, *args_list)

def cmd_test():
    """Runs the end-to-end truth tests (routing validation)."""
    path = CONTROL_PLANE / "config" / "health.py"
    return run_script(path)

def cmd_init(args):
    """Initializes the M3TAL environment."""
    path = CONTROL_PLANE / "init.py"
    code = 0
    if args.repair:
        code = run_script(path, f"--repair={args.repair}", check=True)
    else:
        code = run_script(path, check=True)
    
    # Bootstrap Guard: Automatically audit after init
    print("\n[INIT] Performing post-bootstrap infrastructure audit...")
    return cmd_audit(args)

def cmd_run():
    """Launches the main Control Plane supervisor."""
    path = AGENTS_DIR / "run.py"
    return run_script(path)

# --- CLI Structure ------------------------------------------------------------
def main():
    if not ROOT:
        print("[X] FATAL: Could not locate M3TAL repository root.")
        print("   Please run this from within the M3TAL project folder.")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        prog="m3tal",
        description="M3TAL Control Plane - Production Tooling CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # logs [stack|all]
    p_logs = subparsers.add_parser("logs", help="Stream redacted and secure Docker logs")
    p_logs.add_argument("stack", nargs="?", default="all", help="Target stack name or 'all' (default: all)")
    p_logs.add_argument("--alerts", action="store_true", help="Enable proactive Telegram alerting")

    # env
    subparsers.add_parser("env", help="Run hardened environment audit (masked secrets)")

    # audit
    p_audit = subparsers.add_parser("audit", help="Audit Docker networking and Traefik contracts")
    p_audit.add_argument("--json", action="store_true", help="Output audit results in machine-readable JSON")

    # test
    subparsers.add_parser("test", help="Run end-to-end routing 'Truth Tests'")

    # init
    p_init = subparsers.add_parser("init", help="Run system initialization and bootstrap")
    p_init.add_argument("--repair", help="Repair scope (e.g. all, docker, fs, state, logs)")

    # run
    subparsers.add_parser("run", help="Start the persistent Control Plane agent")

    # If no args, show help
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    # Context Guard: Ensure we have a valid environment before any command
    if not (ROOT / ".env").exists():
        print("[X] FATAL: Missing .env file at repository root.")
        print(f"   Searching in: {ROOT}")
        sys.exit(1)

    if args.command == "logs":
        sys.exit(cmd_logs(args))
    elif args.command == "env":
        sys.exit(cmd_env())
    elif args.command == "audit":
        sys.exit(cmd_audit(args))
    elif args.command == "test":
        sys.exit(cmd_test())
    elif args.command == "init":
        sys.exit(cmd_init(args))
    elif args.command == "run":
        sys.exit(cmd_run())
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
