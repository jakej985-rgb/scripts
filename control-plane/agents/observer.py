import sys
import os
import time
import collections

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import LOG_DIR, STATE_DIR
from utils.guards import wrap_agent
from utils.logger import get_logger
from utils.state import load_json, save_json

logger = get_logger("observer")
SEEN_EVENTS_JSON = os.path.join(STATE_DIR, "observer_seen.json")
_seen_events: set[str] = set(load_json(SEEN_EVENTS_JSON, default=[]))

def aggregate_events():
    """Phase 2: Observer Agent as per Audit Batch 4 T5."""
    # This agent scans agent logs and generates a unified event stream
    logger.info("Watching system logs for critical events...")
    
    # Audit fix 2.15: implementation of log scavenging
    for file in os.listdir(LOG_DIR):
        if file.endswith(".log") and file != "observer.log":
            agent_name = file.replace(".log", "")
            path = os.path.join(LOG_DIR, file)
            try:
                with open(path, "r") as f:
                    # Only check the last 100 lines to avoid overhead
                    lines = collections.deque(f, maxlen=100)
                    new_event = False
                    for line in lines:
                        # Audit fix 2.15: exclude [ERROR] found inside observer's own detected messages
                        if "Critical Event detected" in line:
                            continue
                        if "[ERROR]" in line or "[CRASH]" in line:
                            fingerprint = f"{agent_name}:{line.strip()[-80:]}"
                            if fingerprint in _seen_events:
                                continue
                            
                            _seen_events.add(fingerprint)
                            new_event = True
                            
                            # Audit fix 2.4: Bounded Sliding Window rotation
                            if len(_seen_events) > 500:
                                # Remove oldest 100 entries instead of clearing everything
                                ordered = list(_seen_events)
                                _seen_events = set(ordered[100:])
                                
                            logger.warning(f"Critical Event detected in {agent_name}: {line.strip()}")
                    
                    if new_event:
                        save_json(SEEN_EVENTS_JSON, list(_seen_events))

            except Exception as e:
                logger.error(f"Failed to scan log {file}: {e}")

if __name__ == "__main__":
    # Observer runs on all nodes — now uses wrap_agent for proper
    # lock/shutdown/health integration (Audit fix 2.1)
    wrap_agent("observer", aggregate_events)
