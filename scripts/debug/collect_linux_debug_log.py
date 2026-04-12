#!/usr/bin/env python3
import time
import os
import subprocess
from pathlib import Path

# --- Context Anchoring --------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent
STATE_DIR = REPO_ROOT / "control-plane" / "state"
LOG_DIR = STATE_DIR / "logs"

FULL_LOG_FILE = REPO_ROOT / "logs_linux.txt"
ERROR_LOG_FILE = REPO_ROOT / "error_log_linux.txt"

ERROR_KEYWORDS = ["[ERROR]", "[FATAL]", "EXCEPTION", "✖", "FAIL", "CRITICAL", "non-zero exit status"]

def run_cmd(cmd_list, label):
    """Safely run a system command and return output."""
    try:
        res = subprocess.run(cmd_list, capture_output=True, text=True, timeout=15)
        return f"\n--- {label} ---\n{res.stdout if res.returncode == 0 else res.stderr}\n"
    except Exception as e:
        return f"\n--- {label} FAILED ---\n{e}\n"

def collect_logs():
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[*] Starting Linux debug log collection at {ts}...")
    
    try:
        # Open both files
        with open(FULL_LOG_FILE, "w", encoding="utf-8") as full_f, \
             open(ERROR_LOG_FILE, "w", encoding="utf-8") as err_f:
            
            header = f"M3TAL SYSTEM DEBUG BUNDLE (LINUX)\nGenerated: {ts}\nRepo Root: {REPO_ROOT}\n" + ("=" * 80) + "\n\n"
            full_f.write(header)
            err_f.write(f"M3TAL ERROR LOG (LINUX)\nGenerated: {ts}\n" + ("=" * 80) + "\n\n")

            def write_dual(text, only_full=False):
                full_f.write(text)
                if not only_full:
                    # Logic to extract error lines from a block of text
                    for line in text.splitlines():
                        if any(kw.lower() in line.lower() for kw in ERROR_KEYWORDS):
                            err_f.write(line + "\n")

            # 1. System Info
            sys_info = "--- LINUX SYSTEM INFO ---\n"
            sys_info += run_cmd(["uname", "-a"], "Kernel Info")
            sys_info += run_cmd(["hostname"], "Hostname")
            sys_info += run_cmd(["docker", "version"], "Docker Version")
            sys_info += run_cmd(["docker", "ps", "-a"], "Docker Container Status")
            sys_info += run_cmd(["ip", "addr"], "Network Configuration")
            sys_info += run_cmd(["df", "-h"], "Disk Space Usage")
            write_dual(sys_info)
            
            # 2. M3TAL State Verification
            core_state = "\n" + ("=" * 80) + "\n--- M3TAL CORE STATE ---\n"
            leader_file = STATE_DIR / "leader.txt"
            if leader_file.exists():
                core_state += f"[LEADER]: {leader_file.read_text(encoding='utf-8', errors='replace').strip()}\n"
            health_file = STATE_DIR / "health.json"
            if health_file.exists():
                core_state += f"[HEALTH]: {health_file.read_text(encoding='utf-8', errors='replace').strip()}\n"
            write_dual(core_state)

            # 3. Docker Stack Logs (Last 100 lines per critical service)
            docker_logs = "\n" + ("=" * 80) + "\n--- DOCKER STACK LOGS ---\n"
            critical_containers = ["traefik", "cloudflared", "gluetun", "m3tal-dashboard"]
            for container in critical_containers:
                docker_logs += run_cmd(["docker", "logs", "--tail", "100", container], f"Container Logs: {container}")
            write_dual(docker_logs)

            # 4. Component Log Collection (The .log files)
            write_dual("\n" + ("=" * 80) + "\n--- COMPONENT LOG COLLECTION ---\n", only_full=True)
            if not LOG_DIR.exists():
                write_dual(f"[FATAL] Log directory missing: {LOG_DIR}\n")
            else:
                for filename in sorted(os.listdir(LOG_DIR)):
                    if not filename.endswith(".log"):
                        continue
                        
                    log_path = LOG_DIR / filename
                    write_dual(f"\n--- ATTACHMENT: {filename} ---\n", only_full=True)
                    
                    try:
                        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                            lines = f.readlines()
                            # Tail 1000 lines for the bundle
                            tail = lines[-1000:]
                            write_dual(f"  (Processing last {len(tail)} lines)\n")
                            for line in tail:
                                full_f.write(line)
                                if any(kw.lower() in line.lower() for kw in ERROR_KEYWORDS):
                                    err_f.write(f"[{filename}] {line}")
                    except Exception as e:
                        write_dual(f"\n[ERROR] Could not read log file {filename}: {e}\n")

        print(f"[+] Linux logs ready:\n    Full:  {FULL_LOG_FILE}\n    Error: {ERROR_LOG_FILE}")
    except Exception as e:
        print(f"[FATAL] Collection failed: {e}")

if __name__ == "__main__":
    collect_logs()
