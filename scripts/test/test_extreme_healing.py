#!/usr/bin/env python3
"""
Extreme Healing Test Suite
Simulates brutal system failures and verifies autonomous recovery.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = REPO_ROOT / "control-plane" / "state"
LOG_DIR = STATE_DIR / "logs"
INIT_PY = REPO_ROOT / "control-plane" / "init.py"

def run_init(args=None):
    cmd = [sys.executable, str(INIT_PY)]
    if args: cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True)

def test_log_lockout():
    print("\n[TEST] Simulating individual log file lockout (chmod 000)...")
    monitor_log = LOG_DIR / "monitor.log"
    monitor_log.touch()
    os.chmod(monitor_log, 0o000)
    
    res = run_init(["--repair=logs"])
    print(f"Result: {res.stdout.strip()}")
    # Init should continue even if monitor.log is locked (fallback to stdout)
    assert res.returncode == 0
    print("✅ Passed: System avoided crash during log lockout.")

def test_state_dir_lockout():
    print("\n[TEST] Simulating state directory lockout (chmod 000)...")
    if os.name == "nt":
        print("Skipping chmod 000 test on Windows (unsupported).")
        return
        
    os.chmod(STATE_DIR, 0o000)
    try:
        res = run_init()
        # This SHOULD fail as state is a critical dependency for readiness
        print(f"Result (Exit {res.returncode}): {res.stderr.strip()}")
        assert res.returncode != 0
        print("✅ Passed: System correctly identified fatal state failure.")
    finally:
        os.chmod(STATE_DIR, 0o755)

def test_corrupt_json():
    print("\n[TEST] Simulating corrupted state JSON...")
    metrics_json = STATE_DIR / "metrics.json"
    metrics_json.write_text("NOT_JSON{]{_corrupted", encoding="utf-8")
    
    res = run_init()
    assert res.returncode == 0
    # Repair check
    import json
    with open(metrics_json, 'r') as f:
        data = json.load(f)
        assert "system" in data
    print("✅ Passed: Corrupted JSON was autonomously reset.")

def test_concurrency_locking():
    print("\n[TEST] Simulating concurrency (init vs healer)...")
    # 1. Create a "manual" lock
    lock_file = STATE_DIR / "healer.lock"
    lock_file.write_text("9999@fakehost")
    
    res = run_init()
    # Should exit immediately as lock is active and not stale
    assert "Another instance/healer is active" in res.stdout
    print("✅ Passed: Locking system prevented concurrent execution.")
    
    # 2. Test stale lock
    print("[TEST] Testing stale lock recovery...")
    # Set mtime to 1 hour ago
    stale_time = time.time() - 3601
    os.utime(lock_file, (stale_time, stale_time))
    
    res = run_init()
    assert res.returncode == 0
    assert "Removing stale lock" in res.stdout
    print("✅ Passed: Stale lock was correctly detected and removed.")

if __name__ == "__main__":
    import sys
    try:
        test_log_lockout()
        test_corrupt_json()
        test_concurrency_locking()
        test_state_dir_lockout()
        print("\n--- ALL EXTREME TESTS PASSED ---")
    except Exception as e:
        print(f"\n❌ TEST SUITE FAILED: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        try:
            os.chmod(LOG_DIR / "monitor.log", 0o644)
            (STATE_DIR / "healer.lock").unlink(missing_ok=True)
        except: pass
