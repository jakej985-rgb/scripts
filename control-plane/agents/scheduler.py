import sys
import os
import time

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import CLUSTER_YML, NORMALIZED_METRICS_JSON, DECISIONS_JSON
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("scheduler")

def get_best_node(nodes_metrics):
    best_node = None
    lowest_score = 999
    
    for node, metrics in nodes_metrics.items():
        # Score = CPU + Mem + (Estimated count if available)
        cpu = metrics.get("cpu", 0)
        mem = metrics.get("mem", 0)
        score = cpu + mem
        
        if score < lowest_score:
            lowest_score = score
            best_node = node
            
    return best_node

def schedule():
    """Phase 2: Python Scheduler as per Audit Batch 2 T6."""
    # This agent currently just identifies the best node for new deployments
    # but doesn't auto-migrate yet (safety fast).
    
    metrics = load_json(NORMALIZED_METRICS_JSON, default={})
    if not metrics:
        logger.info("No node metrics available for scheduling.")
        return

    best = get_best_node(metrics)
    if best:
        logger.info(f"Recommended node for placement: {best}")
    
    # We could write this recommendation to state if decision.py needs it
    # Currently, server.py handles it dynamically.

if __name__ == "__main__":
    wrap_agent("scheduler", schedule)
