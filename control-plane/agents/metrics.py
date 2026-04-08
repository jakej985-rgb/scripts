import subprocess
import json
import sys
import os
import time

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import METRICS_JSON
from utils.state import save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("metrics")

def get_system_metrics():
    metrics = {
        "cpu": 0.0,
        "mem": 0.0,
        "timestamp": int(time.time())
    }
    
    try:
        # CPU
        if sys.platform != "win32":
            cpu_cmd = "grep 'cpu ' /proc/stat | awk '{print ($2+$4)*100/($2+$4+$5)}'"
            res = subprocess.run(cpu_cmd, shell=True, capture_output=True, text=True)
            metrics["cpu"] = round(float(res.stdout.strip()), 2) if res.stdout.strip() else 0.0
            
            # Memory
            mem_cmd = "free | grep Mem | awk '{print $3/$2 * 100.0}'"
            res = subprocess.run(mem_cmd, shell=True, capture_output=True, text=True)
            metrics["mem"] = round(float(res.stdout.strip()), 2) if res.stdout.strip() else 0.0
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        
    return metrics

def get_container_metrics():
    container_stats = []
    try:
        # Get stats for all running containers
        cmd = ["docker", "stats", "--no-stream", "--format", "{{json .}}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        for line in result.stdout.strip().split('\n'):
            if line:
                raw = json.loads(line)
                # Clean up percentage strings (e.g. "1.23%" -> 1.23)
                cpu_p = float(raw.get("CPUPerc", "0").replace("%", ""))
                mem_p = float(raw.get("MemPerc", "0").replace("%", ""))
                
                container_stats.append({
                    "name": raw.get("Name"),
                    "cpu": cpu_p,
                    "mem": mem_p,
                    "mem_usage": raw.get("MemUsage"),
                    "net_io": raw.get("NetIO"),
                    "block_io": raw.get("BlockIO")
                })
    except Exception as e:
        logger.error(f"Failed to get container metrics: {e}")
        
    return container_stats

def collect_all_metrics():
    """Phase 1: Deep Metrics as per Audit Batch 2 T4."""
    system = get_system_metrics()
    containers = get_container_metrics()
    
    data = {
        "system": system,
        "containers": containers,
        "timestamp": system["timestamp"],
        # Legacy field for backward compatibility with anomaly.py
        "cpu": system["cpu"] 
    }
    
    if save_json(METRICS_JSON, data):
        logger.info(f"Captured metrics for {len(containers)} containers.")
    else:
        logger.error("Failed to save metrics.json")

if __name__ == "__main__":
    wrap_agent("metrics", collect_all_metrics)
