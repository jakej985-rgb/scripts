#!/usr/bin/env python3
import time
import os
from pathlib import Path

# --- Context Anchoring --------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
STATE_DIR = REPO_ROOT / "control-plane" / "state"
LOG_DIR = STATE_DIR / "logs"

OUTPUT_FILE = REPO_ROOT / "debug_bundle.txt"

def collect_logs():
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[*] Starting debug log collection at {ts}...")
    
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as bundle:
            bundle.write(f"M3TAL SYSTEM DEBUG BUNDLE\n")
            bundle.write(f"Generated: {ts}\n")
            bundle.write(f"Repo Root: {REPO_ROOT}\n")
            bundle.write("=" * 80 + "\n\n")

            # 1. State Verification
            bundle.write("--- CORE STATE ---\n")
            leader_file = STATE_DIR / "leader.txt"
            if leader_file.exists():
                bundle.write(f"[LEADER]: {leader_file.read_text(encoding='utf-8').strip()}\n")
            else:
                bundle.write("[LEADER]: Missing\n")
            
            bundle.write("\n" + "=" * 80 + "\n\n")

            # 2. Log Collection
            if not LOG_DIR.exists():
                bundle.write(f"[FATAL] Log directory missing: {LOG_DIR}\n")
                return

            # Explicitly iterate names to avoid issues with some globbing patterns on Windows
            for filename in os.listdir(LOG_DIR):
                if not filename.endswith(".log"):
                    continue
                    
                log_path = LOG_DIR / filename
                bundle.write(f"--- ATTACHMENT: {filename} ---\n")
                
                try:
                    # Windows Tip: Some logs might be locked. Open in non-exclusive mode.
                    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                        tail = lines[-500:] # Last 500 lines
                        bundle.write(f" (Showing last {len(tail)} lines)\n\n")
                        bundle.writelines(tail)
                except Exception as e:
                    bundle.write(f"\n[ERROR] Could not read log file: {e}\n")
                
                bundle.write("\n" + "-" * 40 + "\n\n")

        print(f"[+] Debug bundle ready: {OUTPUT_FILE}")
    except Exception as e:
        print(f"[FATAL] Collection failed: {e}")

if __name__ == "__main__":
    collect_logs()
