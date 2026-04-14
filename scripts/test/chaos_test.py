import os
import random
import time
import sys

# Standardize path resolution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import METRICS_JSON, NORMALIZED_METRICS_JSON, ANOMALIES_JSON, DECISIONS_JSON
from utils.state import load_json, save_json
from utils.logger import get_logger

logger = get_logger("chaos")

# We use the new chaos_events.json via its absolute path from utils
from utils.paths import STATE_DIR
CHAOS_EVENTS_JSON = os.path.join(STATE_DIR, "chaos_events.json")

TARGET_FILES = [
    METRICS_JSON,
    NORMALIZED_METRICS_JSON,
    ANOMALIES_JSON,
    DECISIONS_JSON
]

CHAOS_INTERVAL = int(os.getenv("CHAOS_INTERVAL", "30"))

def log_chaos_event(action, target):
    event = {
        "timestamp": int(time.time()),
        "action": action,
        "target": os.path.basename(target),
        "resolved": False
    }
    events = load_json(CHAOS_EVENTS_JSON, default=[])
    events.append(event)
    # Keep last 20 events
    save_json(CHAOS_EVENTS_JSON, events[-20:])

def corrupt_file(path):
    try:
        with open(path, "w") as f:
            f.write("CORRUPTED_NON_JSON_DATA_!!!")
        return True
    except Exception as e:
        logger.error(f"Chaos failed to corrupt: {e}")
        return False

def delete_file(path):
    try:
        if os.path.exists(path):
            os.remove(path)
            return True
    except Exception as e:
        logger.error(f"Chaos failed to delete: {e}")
    return False

def empty_file(path):
    try:
        with open(path, "w") as f:
            f.write("")
        return True
    except Exception as e:
        logger.error(f"Chaos failed to empty: {e}")
    return False

def chaos_action():
    target_path = random.choice(TARGET_FILES)
    file_name = os.path.basename(target_path)

    # Weights: Corrupt (20), Delete (20), Empty (10), Noop (50)
    action = random.choices(
        ["corrupt", "delete", "empty", "noop"],
        weights=[20, 20, 10, 50],
        k=1
    )[0]

    if action == "noop":
        logger.info("🛡️ CHAOS: System spared this round")
        return

    success = False
    if action == "corrupt":
        success = corrupt_file(target_path)
    elif action == "delete":
        success = delete_file(target_path)
    elif action == "empty":
        success = empty_file(target_path)

    if success:
        logger.warning(f"💥 CHAOS: Applied {action} to {file_name}")
        log_chaos_event(action, target_path)

def main():
    logger.info(f"Chaos Test Agent Active (Interval: {CHAOS_INTERVAL}s)")
    while True:
        chaos_action()
        time.sleep(CHAOS_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Chaos Test Agent CRASHED: {e}")
