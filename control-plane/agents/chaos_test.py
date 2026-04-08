import os
import random
import time
import sys

# Standardize path resolution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR, METRICS_JSON, NORMALIZED_METRICS_JSON, ANOMALIES_JSON, DECISIONS_JSON
from utils.logger import get_logger

logger = get_logger("chaos")

TARGET_FILES = [
    METRICS_JSON,
    NORMALIZED_METRICS_JSON,
    ANOMALIES_JSON,
    DECISIONS_JSON
]

# Stress mode control via environment
CHAOS_INTERVAL = int(os.getenv("CHAOS_INTERVAL", "30"))

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

    # Weights: Corrupt (2), Delete (2), Empty (1), Noop (5)
    action = random.choices(
        ["corrupt", "delete", "empty", "noop"],
        weights=[20, 20, 10, 50],
        k=1
    )[0]

    if action == "corrupt":
        if corrupt_file(target_path):
            logger.warning(f"💥 CHAOS: Corrupted {file_name}")
    elif action == "delete":
        if delete_file(target_path):
            logger.warning(f"💥 CHAOS: Deleted {file_name}")
    elif action == "empty":
        if empty_file(target_path):
            logger.warning(f"💥 CHAOS: Emptied {file_name}")
    else:
        logger.info("🛡️ CHAOS: System spared this round")

def main():
    logger.info(f"Chaos Test Agent Active (Interval: {CHAOS_INTERVAL}s)")
    logger.info(f"Monitoring state files in: {STATE_DIR}")

    while True:
        chaos_action()
        time.sleep(CHAOS_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Chaos Test Agent stopped by user.")
    except Exception as e:
        logger.critical(f"Chaos Test Agent CRASHED: {e}")
