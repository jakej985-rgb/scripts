import os
import json
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(BASE_DIR, "state")

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


def log(msg):
    print(f"[HEALTH] {msg}")


def is_valid_json(path):
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
    log("Health scoring started")

    while True:
        score = 100
        issues = []

        for f in FILES:
            path = os.path.join(STATE_DIR, f)
            status = get_status(path)

            prev = file_state.get(f, "ok")

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

        log(f"SYSTEM HEALTH: {score}% | {verdict}")

        if issues:
            for i in issues:
                log(f"ISSUE: {i}")

        # Phase 4 — Write to state
        try:
            with open(os.path.join(STATE_DIR, "health.json"), "w") as f_out:
                json.dump({
                    "score": score,
                    "verdict": verdict,
                    "issues": issues,
                    "timestamp": time.time()
                }, f_out, indent=2)
        except Exception as e:
            log(f"Failed to write health.json: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"CRASHED: {e}")
