import sys
import time
from pathlib import Path

# Add control-plane and agents to path
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(repo_root / "control-plane"))
sys.path.append(str(repo_root / "control-plane" / "agents"))

from docker_logs_agent import redact, load_secrets, normalize, should_alert, get_severity

def test_phase5_logic():
    secrets = load_secrets()
    print(f"Loaded {len(secrets)} secrets.")
    
    print("\n--- 1. Normalization & Deduplication Test ---")
    # Patterns that should be considered "the same"
    m1 = "ERROR: Failed to connect to DB at 10:00:01 (retry 1)"
    m2 = "ERROR: Failed to connect to DB at 10:00:02 (retry 2)"
    
    print(f"M1: {m1}")
    print(f"M2: {m2}")
    
    print(f"M1 Normalized: {normalize(m1)}")
    print(f"M2 Normalized: {normalize(m2)}")
    
    print(f"Alert 1 (M1): {should_alert(m1)}") # Should be True
    # Wait a bit but less than multiline window? No, multiline window is 2s.
    # To test deduplication, we need to wait more than 2s but less than 60s.
    time.sleep(2.1) 
    print(f"Alert 2 (M2): {should_alert(m2)}") # Should be False (deduplicated)
    
    print("\n--- 2. Hex/Hash Normalization ---")
    h1 = "Exception in container 1a2b3c4d5e6f: memory leak"
    h2 = "Exception in container f6e5d4c3b2a1: memory leak"
    print(f"H1: {h1}")
    print(f"H2: {h2}")
    print(f"H1 Normalized: {normalize(h1)}")
    print(f"H2 Normalized: {normalize(h2)}")
    
    print("\n--- 3. Multi-line / Burst Suppression ---")
    line1 = "Traceback (most recent call last):"
    line2 = "  File \"app.py\", line 10, in main"
    
    print(f"Burst 1 (L1): {should_alert(line1)}") # Should be True (if cache cleared or new pattern)
    print(f"Burst 2 (L2): {should_alert(line2)}") # Should be False (within 2s window)
    
    print("\n--- 4. Severity Mapping ---")
    cases = [
        "PANIC: Kernel halted!",
        "ERROR: something failed",
        "WARN: high memory usage",
        "INFO: system ok"
    ]
    for c in cases:
        print(f"Line: {c:25} | Severity: {get_severity(c)}")

if __name__ == "__main__":
    # Clear cache for clean test
    import docker_logs_agent
    docker_logs_agent.ALERT_CACHE = {}
    test_phase5_logic()
