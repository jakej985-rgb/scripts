import sys
import os
import subprocess
import argparse
import re
from pathlib import Path

# Batch 16 Hardening: Force UTF-8 for Windows console resilience
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, Exception):
        pass

# M3TAL Unified CLI (v2.2 Production-Grade)
# Responsibility: Centralized entrypoint for all M3TAL orchestration and observability.

# Attempting catastrophic import of paths module
try:
    # Path bootstrap (V6.5.2)

    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / ".env").exists() and (parent / "docker").exists():
            if str(parent / "control-plane") not in sys.path:
                sys.path.append(str(parent / "control-plane"))
            break
            
    from agents.utils.paths import (
        REPO_ROOT, SCRIPTS_DIR, AGENTS_DIR, CONTROL_PLANE
    )
    # Centralized Audit Import (Phase 2)
    from config.audit import run_audit, FAILED as AUDIT_FAILED
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
    """Runs the infrastructure contract auditor (Centralized Import)."""
    json_out = hasattr(args, 'json') and args.json
    strict = hasattr(args, 'strict') and args.strict
    status = run_audit(json_out=json_out, strict=strict)
    return 0 if status != AUDIT_FAILED else 1

def cmd_build(args):
    """Enforces a clean rebuild of the control plane containers."""
    print("\n[BUILD] Triggering no-cache build of M3TAL Control Plane...")
    cmd = ["docker", "compose", "build", "--no-cache", "control-plane"]
    target_stack = REPO_ROOT / "control-plane"
    try:
        subprocess.run(cmd, cwd=str(target_stack), check=True)
        print("[INIT] Build successful. Containers are up to date.")
        return 0
    except Exception as e:
        print(f"[X] Build failed: {e}")
        return 1

def cmd_test():
    """Runs the end-to-end truth tests (routing validation)."""
    path = CONTROL_PLANE / "config" / "health.py"
    return run_script(path)

def cmd_init(args):
    """Initializes the M3TAL environment."""
    path = CONTROL_PLANE / "init.py"
    if args.repair:
        status = run_script(path, f"--repair={args.repair}", check=True)
    else:
        status = run_script(path, check=True)
    
    if status != 0:
        return status

    # Bootstrap Guard: Automatically audit after init
    print("\n[INIT] Performing post-bootstrap infrastructure audit...")
    return cmd_audit(args)

def cmd_run():
    """Launches the main Control Plane supervisor."""
    path = AGENTS_DIR / "run.py"
    return run_script(path)

def cmd_shutdown(args):
    """Executes the Global Blackout or selective shutdown."""
    path = CONTROL_PLANE / "shutdown.py"
    return run_script(path, *args.stacks)

def cmd_heal():
    """Performs lightweight runtime healing (FS, logs, state)."""
    path = CONTROL_PLANE / "init.py"
    return run_script(path, "--repair=fs,logs,state")

def cmd_bootstrap(args):
    """Alias for full system initialization."""
    return cmd_init(args)

def cmd_traefik(args):
    """Handles Traefik-specific orchestration and auditing."""
    if args.subcommand == "audit":
        path = CONTROL_PLANE / "config" / "audit.py"
        args_list = []
        if hasattr(args, 'strict') and args.strict:
            args_list.append("--strict")
        return run_script(path, *args_list)
    elif args.subcommand == "test":
        path = CONTROL_PLANE / "config" / "health.py"
        return run_script(path)
    return 1

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
    p_audit.add_argument("--strict", action="store_true", help="Fail on ANY warnings (CI/CD mode)")

    # traefik [audit|test]
    p_traefik = subparsers.add_parser("traefik", help="Traefik routing operations")
    p_t_sub = p_traefik.add_subparsers(dest="subcommand", help="Traefik subcommand")
    
    p_t_audit = p_t_sub.add_parser("audit", help="Verify labels vs Traefik runtime API")
    p_t_audit.add_argument("--strict", action="store_true", help="Fail on warnings")
    
    p_t_sub.add_parser("test", help="Execute curl-based truth tests")

    # test (Shortcut for m3tal traefik test)
    subparsers.add_parser("test", help="Run end-to-end routing 'Truth Tests'")

    # init
    p_init = subparsers.add_parser("init", help="Run system initialization and bootstrap")
    p_init.add_argument("--repair", help="Repair scope (e.g. all, docker, fs, state, logs)")

    # run
    subparsers.add_parser("run", help="Start the persistent Control Plane agent")

    # shutdown [stacks...]
    p_shutdown = subparsers.add_parser("shutdown", help="Safely stop M3TAL agents and Docker stacks")
    p_shutdown.add_argument("stacks", nargs="*", help="Optional specific stacks to stop (default: all)")

    # heal
    subparsers.add_parser("heal", help="Run lightweight runtime healing (FS, logs, state)")

    # build
    subparsers.add_parser("build", help="Enforce no-cache rebuild of control-plane agents")

    # bootstrap
    p_bootstrap = subparsers.add_parser("bootstrap", help="Full system initialization and first-run orchestration")
    p_bootstrap.add_argument("--repair", help="Repair scope (e.g. all, docker, fs, state, logs)")

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

    # Load .env into os.environ so subprocesses (audit, health, etc.) inherit values
    with open(ROOT / ".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # Handle optional 'export ' prefix
            if line.startswith("export "):
                line = line[len("export "):].strip()
                
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                
                # Only strip inline comments preceded by whitespace (preserve # in values)
                v = re.sub(r'\s+#.*$', '', v).strip()
                
                # Strip quotes
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                    
                os.environ[k] = v

    if args.command == "logs":
        sys.exit(cmd_logs(args))
    elif args.command == "env":
        sys.exit(cmd_env())
    elif args.command == "audit":
        sys.exit(cmd_audit(args))
    elif args.command == "traefik":
        sys.exit(cmd_traefik(args))
    elif args.command == "test":
        sys.exit(cmd_test())
    elif args.command == "init":
        sys.exit(cmd_init(args))
    elif args.command == "run":
        sys.exit(cmd_run())
    elif args.command == "shutdown":
        sys.exit(cmd_shutdown(args))
    elif args.command == "heal":
        sys.exit(cmd_heal())
    elif args.command == "build":
        sys.exit(cmd_build(args))
    elif args.command == "bootstrap":
        sys.exit(cmd_bootstrap(args))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
