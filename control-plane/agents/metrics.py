import subprocess
import json
import sys
import os
import yaml

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import CLUSTER_YML, NORMALIZED_METRICS_JSON
from utils.state import save_json
from utils.logger import get_logger

logger = get_logger("metrics")

def get_cpu_usage(host):
    """Calculate CPU usage on a node via /proc/stat"""
    cpu_cmd = "grep 'cpu ' /proc/stat | awk '{print ($2+$4)*100/($2+$4+$5)}'"
    
    try:
        if host == "localhost":
            result = subprocess.run(cpu_cmd, shell=True, capture_output=True, text=True, check=True)
        else:
            ssh_cmd = ["ssh", "-o", "ConnectTimeout=2", host, cpu_cmd]
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, check=True)
            
        cpu_val = result.stdout.strip()
        return float(cpu_val) if cpu_val else 0.0
    except Exception as e:
        logger.warning(f"Failed to get CPU metrics for {host}: {e}")
        return 0.0

def aggregate_metrics():
    try:
        if not os.path.exists(CLUSTER_YML):
            logger.error(f"Cluster config not found at {CLUSTER_YML}")
            return

        with open(CLUSTER_YML, 'r') as f:
            cluster = yaml.safe_load(f)
        
        nodes = cluster.get('nodes', {})
        metrics = {}
        
        for name, info in nodes.items():
            logger.info(f"Collecting metrics for node: {name}")
            host = info.get('host', 'localhost')
            cpu = get_cpu_usage(host)
            metrics[name] = {"cpu": round(cpu, 2)}
            
        if save_json(NORMALIZED_METRICS_JSON, metrics):
            logger.info(f"Saved cluster metrics to {NORMALIZED_METRICS_JSON}")
            
    except Exception as e:
        logger.error(f"Error in metrics aggregation: {e}")

if __name__ == "__main__":
    aggregate_metrics()
