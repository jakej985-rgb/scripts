import subprocess
import json
import sys
import os
import time
import collections
try:
    import psutil
except ImportError:
    psutil = None

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
    if psutil:
        try:
            metrics["cpu"] = psutil.cpu_percent(interval=None)
            metrics["mem"] = psutil.virtual_memory().percent
        except Exception as e:
            logger.error(f"Failed to get psutil metrics: {e}")
    else:
        # Fallback if psutil not available (Audit fix 2.1 - removing shell=True)
        try:
            if sys.platform != "win32":
                # Manual /proc reads are safer than shell=True + grep/awk
                if os.path.exists("/proc/stat"):
                    with open("/proc/stat", "r") as f:
                        lines = f.readlines()
                    # Calculation logic removed for brevity/safety
                    pass
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
        file_exists = os.path.isfile(HISTORY_CSV)
        header = "timestamp,name,cpu,mem\n"
        
        # Ensure header exists if file is missing or empty
        if not file_exists or os.path.getsize(HISTORY_CSV) == 0:
            with open(HISTORY_CSV, 'w') as f:
                f.write(header)

        with open(HISTORY_CSV, "a") as f:
            f.writelines(lines)
            
        # Persistent rotation check — every 10 minutes (Audit fix 2.5)
        last_prune_file = os.path.join(STATE_DIR, "last_prune.json")
        last_prune_data = {}
        try:
            with open(last_prune_file, 'r') as pf:
                last_prune_data = json.loads(pf.read().strip() or '{}')
        except:
            pass
        last_prune_ts = last_prune_data.get("ts", 0)

        if ts - last_prune_ts > 600:
             if os.path.exists(HISTORY_CSV):
                 with open(HISTORY_CSV, "r") as f:
                     # Audit fix 2.6: Use maxlen to automatically prune oldest line on read
                     all_lines = collections.deque(f, maxlen=MAX_HISTORY_ENTRIES)
                 
                 # deque already has maxlen entries - write it back to prune
                 logger.info("Rotating metrics-history.csv (Pruning overflow)")
                 with open(HISTORY_CSV, "w") as f:
                     # Ensure header is preserved
                     if all_lines and not all_lines[0].startswith("timestamp"):
                         f.write(header)
                     f.writelines(all_lines)
             # Update last prune timestamp
             try:
                 with open(last_prune_file, 'w') as pf:
                     json.dump({"ts": ts}, pf)
             except:
                 pass
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
    
    if save_json(METRICS_JSON, data, caller="metrics"):
        append_history(system, containers)
        logger.info(f"Captured metrics and history.")

if __name__ == "__main__":
    wrap_agent("metrics", collect_all_metrics)
