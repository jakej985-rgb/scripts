import subprocess
import json
import sys
import os
import yaml

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import CLUSTER_YML, NORMALIZED_METRICS_JSON
from utils.state import save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("metrics")

def get_cpu_usage(host):
    cpu_cmd = "grep 'cpu ' /proc/stat | awk '{print ($2+$4)*100/($2+$4+$5)}'"
    if host == "localhost":
        result = subprocess.run(cpu_cmd, shell=True, capture_output=True, text=True, check=True)
    else:
        ssh_cmd = ["ssh", "-o", "ConnectTimeout=2", host, cpu_cmd]
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, check=True)
    cpu_val = result.stdout.strip()
    return float(cpu_val) if cpu_val else 0.0

def aggregate_metrics():
    # Rule #1: NEVER trust input files
    if not os.path.exists(CLUSTER_YML):
        logger.error(f"Config missing: {CLUSTER_YML}. Outputting empty metrics.")
        save_json(NORMALIZED_METRICS_JSON, {})
        return

    with open(CLUSTER_YML, 'r') as f:
        cluster = yaml.safe_load(f) or {}
    
    nodes = cluster.get('nodes', {})
    metrics = {}
    
    for name, info in nodes.items():
        host = info.get('host', 'localhost')
        try:
            cpu = get_cpu_usage(host)
            metrics[name] = {"cpu": round(cpu, 2)}
        except Exception:
            # Rule #4: Fail closed for individual node failure
            metrics[name] = {"cpu": 0.0}
            
    save_json(NORMALIZED_METRICS_JSON, metrics)

if __name__ == "__main__":
    wrap_agent("metrics", aggregate_metrics)
