import sys
import os
import subprocess
import argparse
from pathlib import Path

# M3TAL Unified CLI (v2.2 Production-Grade)
# Responsibility: Centralized entrypoint for all M3TAL orchestration and observability.

# --- Root Detection (Hardened) -------------------------------------------------
def find_root():
    """Auto-detect repo root by walking up parents until .env + docker/ are found."""
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / ".env").exists() and (parent / "docker").exists():
            return parent
    # Check CWD as final fallback
    cwd = Path.cwd()
    if (cwd / ".env").exists() and (cwd / "docker").exists():
        return cwd
    return None

ROOT = find_root()

# --- Execution Helpers --------------------------------------------------------
def run_script(path, *args, check=False):
    """Executes an internal script while passing repo-root context."""
    if not path.exists():
        print(f"❌ Error: Script not found at {path}")
        return
    
    cmd = [sys.executable, str(path)] + list(args)
    try:
        # We don't use 'check=True' for long-running agents so they can be 
        # interrupted with Ctrl+C without showing a traceback.
        return subprocess.run(cmd, check=check)
    except KeyboardInterrupt:
        print("\n👋 Operation cancelled by user.")
        return None

# --- Command Handlers ---------------------------------------------------------
def cmd_logs(args):
    """Starts the Docker logs agent."""
    path = ROOT / "control-plane" / "agents" / "docker_logs_agent.py"
    # Forward arguments
    args_list = [args.stack]
    if args.alerts:
        args_list.append("--alerts")
    run_script(path, *args_list)

def cmd_env():
    """Launches the environment audit tool."""
    path = ROOT / "scripts" / "view_env.py"
    run_script(path)

def cmd_audit(args):
    """Runs the infrastructure contract auditor."""
    path = ROOT / "control-plane" / "config" / "audit.py"
    args_list = []
    if hasattr(args, 'json') and args.json:
        args_list.append("--json")
    # We call it as a module or script
    run_script(path, *args_list)

def cmd_test():
    """Runs the end-to-end truth tests (routing validation)."""
    path = ROOT / "control-plane" / "config" / "health.py"
    run_script(path)

def cmd_init(args):
    """Initializes the M3TAL environment."""
    path = ROOT / "control-plane" / "init.py"
    if args.repair:
        run_script(path, f"--repair={args.repair}", check=True)
    else:
        run_script(path, check=True)
    
    # Bootstrap Guard: Automatically audit after init
    print("\n[INIT] Performing post-bootstrap infrastructure audit...")
    cmd_audit(args)

def cmd_run():
    """Launches the main Control Plane supervisor."""
    path = ROOT / "control-plane" / "run.py"
    run_script(path)

# --- CLI Structure ------------------------------------------------------------
def main():
    if not ROOT:
        print("❌ FATAL: Could not locate M3TAL repository root.")
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
        print("❌ FATAL: Missing .env file at repository root.")
        print(f"   Searching in: {ROOT}")
        sys.exit(1)

    if args.command == "logs":
        cmd_logs(args)
    elif args.command == "env":
        cmd_env()
    elif args.command == "audit":
        cmd_audit(args)
    elif args.command == "test":
        cmd_test()
    elif args.command == "init":
        cmd_init(args)
    elif args.command == "run":
        cmd_run()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
