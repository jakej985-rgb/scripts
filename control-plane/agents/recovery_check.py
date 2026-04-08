import os
import json
import time
import sys

# Standardize path resolution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR, METRICS_JSON, NORMALIZED_METRICS_JSON, ANOMALIES_JSON, DECISIONS_JSON

FILES = {
    "metrics.json": METRICS_JSON,
    "normalized_metrics.json": NORMALIZED_METRICS_JSON,
    "anomalies.json": ANOMALIES_JSON,
    "decisions.json": DECISIONS_JSON
}

file_states = {}

def log(msg):
    print(f"[RECOVERY] {msg}")

def is_valid_json(path):
    if not os.path.exists(path):
        return False
    try:
        with open(path) as f:
            json.load(f)
        return True
    except:
        return False

def get_status(path):
    if not os.path.exists(path):
        return "missing"
    if not is_valid_json(path):
        return "corrupt"
    return "ok"

def main():
    log("Recovery checker active")
    
    # Initial state
    for name, path in FILES.items():
        file_states[name] = get_status(path)
    
    while True:
        for name, path in FILES.items():
            current = get_status(path)
            prev = file_states.get(name)
            
            if current != prev:
                log(f"{name}: {prev} -> {current}")
                file_states[name] = current
                
        time.sleep(2)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[RECOVERY] CRASHED: {e}")
