import sys
import os
import collections

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import LOG_DIR, STATE_DIR
from utils.guards import wrap_agent
from utils.logger import get_logger
from utils.state import load_json, save_json

logger = get_logger("observer")
SEEN_EVENTS_JSON = os.path.join(STATE_DIR, "observer_seen.json")
# Audit Fix H4: Use OrderedDict (keys only) for deterministic eviction
_seen_events = collections.OrderedDict.fromkeys(load_json(SEEN_EVENTS_JSON, default=[]))

def aggregate_events():
    """Phase 2: Observer Agent — Scans logs and generates events."""
    logger.info("Watching system logs for critical events...")
    
    any_new = False
    for file in os.listdir(LOG_DIR):
        if file.endswith(".log") and file != "observer.log":
            agent_name = file.replace(".log", "")
            path = os.path.join(LOG_DIR, file)
            try:
                with open(path, "r") as f:
                    # Only check the last 100 lines to avoid overhead
                    lines = collections.deque(f, maxlen=100)
                    for line in lines:
                        # exclude [ERROR] found inside observer's own detected messages
                        if "Critical Event detected" in line:
                            continue
                        if "[ERROR]" in line or "[CRASH]" in line:
                            fingerprint = f"{agent_name}:{line.strip()[-80:]}"
                            if fingerprint in _seen_events:
                                # Update position to mark as most recent
                                _seen_events.move_to_end(fingerprint)
                                continue
                            
                            _seen_events[fingerprint] = None
                            any_new = True
                            logger.warning(f"Critical Event detected in {agent_name}: {line.strip()}")

            except Exception as e:
                logger.error(f"Failed to scan log {file}: {e}")

    # Sliding window eviction — apply once per cycle, not per-line
    # Audit Fix H4: OrderedDict popitem(last=False) evicts the oldest entries (FIFO)
    while len(_seen_events) > 500:
        _seen_events.popitem(last=False)

    # Batch-save: only write JSON if something changed
    if any_new:
        save_json(SEEN_EVENTS_JSON, list(_seen_events), caller="observer")

if __name__ == "__main__":
    # Observer runs on all nodes — now uses wrap_agent for proper
    # lock/shutdown/health integration (Audit fix 2.1)
    wrap_agent("observer", aggregate_events)
