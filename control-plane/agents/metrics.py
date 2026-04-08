import subprocess
import json
import sys
import os
import time

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import METRICS_JSON, STATE_DIR
from utils.state import save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("metrics")
HISTORY_CSV = os.path.join(STATE_DIR, "metrics-history.csv")
MAX_HISTORY_ENTRIES = 5000 

def get_system_metrics():
    metrics = {"cpu": 0.0, "mem": 0.0, "timestamp": int(time.time())}
    try:
        if sys.platform != "win32":
            cpu_cmd = "grep 'cpu ' /proc/stat | awk '{print ($2+$4)*100/($2+$4+$5)}'"
            res = subprocess.run(cpu_cmd, shell=True, capture_output=True, text=True)
            metrics["cpu"] = round(float(res.stdout.strip()), 2) if res.stdout.strip() else 0.0
            mem_cmd = "free | grep Mem | awk '{print $3/$2 * 100.0}'"
            res = subprocess.run(mem_cmd, shell=True, capture_output=True, text=True)
            metrics["mem"] = round(float(res.stdout.strip()), 2) if res.stdout.strip() else 0.0
    except: pass
    return metrics

def get_container_metrics():
    container_stats = []
    try:
        cmd = ["docker", "stats", "--no-stream", "--format", "{{json .}}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        for line in result.stdout.strip().split('\n'):
            if line:
                raw = json.loads(line)
                container_stats.append({
                    "name": raw.get("Name"),
                    "cpu": float(raw.get("CPUPerc", "0").replace("%", "")),
                    "mem": float(raw.get("MemPerc", "0").replace("%", "")),
                    "mem_usage": raw.get("MemUsage"),
                })
    except Exception as e:
        logger.error(f"Failed to get container stats: {e}")
    return container_stats

def append_history(system, containers):
    """Batch 6 T1: Append metrics to history CSV with rotation."""
    ts = system["timestamp"]
    lines = []
    
    # Write system summary
    lines.append(f"{ts},host,{system['cpu']},{system['mem']}\n")
    
    # Write container individual metrics
    for c in containers:
        lines.append(f"{ts},{c['name']},{c['cpu']},{c['mem']}\n")
        
    try:
        with open(HISTORY_CSV, "a") as f:
            f.writelines(lines)
            
        # Optional: truncate at threshold to prevent disk sprawl
        # This keeps the last X lines
        if ts % 600 == 0: # Every 10 min prune
             with open(HISTORY_CSV, "r") as f:
                 all_lines = f.readlines()
             if len(all_lines) > MAX_HISTORY_ENTRIES:
                 logger.info("Rotating metrics-history.csv")
                 with open(HISTORY_CSV, "w") as f:
                     f.writelines(all_lines[-MAX_HISTORY_ENTRIES:])
    except Exception as e:
        logger.error(f"Failed to write history: {e}")

def collect_all_metrics():
    system = get_system_metrics()
    containers = get_container_metrics()
    
    data = {
        "system": system,
        "containers": containers,
        "timestamp": system["timestamp"],
        "cpu": system["cpu"] 
    }
    
    if save_json(METRICS_JSON, data):
        append_history(system, containers)
        logger.info(f"Captured metrics and history.")

if __name__ == "__main__":
    wrap_agent("metrics", collect_all_metrics)
