import os
import sys
import time
import json

# Standardize path resolution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR, HEALTH_JSON
from utils.state import load_json, save_json
from utils.logger import get_logger

logger = get_logger("scorer")

FILES = [
    "metrics.json",
    "normalized_metrics.json",
    "anomalies.json",
    "decisions.json"
]

MAX_RECOVERY_TIME = 15  # seconds
CHECK_INTERVAL = 5

file_state = {}
file_timer = {}

def get_status(path):
    if not os.path.exists(path):
        return "missing"
    data = load_json(path, default=None)
    if data is None:
        return "corrupt"
    return "ok"

def main():
    logger.info("Health scoring started")

    while True:
        score = 100
        issues = []

        for f in FILES:
            path = os.path.join(STATE_DIR, f)
            status = get_status(path)

            # Track bad state duration
            if status in ["missing", "corrupt"]:
                if f not in file_timer:
                    file_timer[f] = time.time()
            else:
                if f in file_timer:
                    duration = time.time() - file_timer[f]

                    if duration > MAX_RECOVERY_TIME:
                        issues.append(f"{f} slow recovery ({int(duration)}s)")
                        score -= 20
                    else:
                        score -= 5

                    del file_timer[f]

            file_state[f] = status

        # Pipeline freshness check
        decision_path = os.path.join(STATE_DIR, "decisions.json")
        if os.path.exists(decision_path):
            age = time.time() - os.path.getmtime(decision_path)
            if age > 30:
                issues.append("decisions stale")
                score -= 30

        # Clamp score
        score = max(score, 0)
        verdict = "PASS" if score >= 70 else "FAIL"

        logger.info(f"SYSTEM HEALTH: {score}% | {verdict}")

        if issues:
            for i in issues:
                logger.warning(f"ISSUE: {i}")

        # Phase 4 — Write to state
        health_data = {
            "score": score,
            "verdict": verdict,
            "issues": issues,
            "timestamp": int(time.time())
        }
        if not save_json(HEALTH_JSON, health_data):
            logger.error("Failed to write health.json")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"CRASHED: {e}", exc_info=True)
