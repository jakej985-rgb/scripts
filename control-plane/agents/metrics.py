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

if psutil:
    # Seed the CPU measurement (Audit fix 2.1)
    psutil.cpu_percent(interval=None)

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import METRICS_JSON, STATE_DIR
from utils.state import save_json, safe_replace
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("metrics")
HISTORY_CSV = os.path.join(STATE_DIR, "metrics-history.csv")
MAX_HISTORY_ENTRIES = 5000 
_last_docker_error_log = 0
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
                    # Audit Fix M1: Basic /proc/stat CPU fallback
                    with open("/proc/stat", "r") as f:
                        line = f.readline()
                    parts = line.split()
                    if len(parts) >= 5:
                        idle = int(parts[4])
                        total = sum(int(p) for p in parts[1:])
                        metrics["cpu"] = round(100.0 * (1.0 - idle / total), 1)
        except Exception as e:
            logger.debug(f"Fallback metrics failed: {e}")
    return metrics

def get_container_metrics():
    container_stats = []
    try:
        # Increased timeout to 30s for slow Windows hosts (Audit fix 4.7)
        cmd = ["docker", "stats", "--no-stream", "--format", "{{json .}}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    raw = json.loads(line)
                    # Normalize percentages (sometimes they have % symbol)
                    cpu_str = str(raw.get("CPUPerc", "0")).replace("%", "")
                    mem_str = str(raw.get("MemPerc", "0")).replace("%", "")
                    container_stats.append({
                        "name": raw.get("Name"),
                        "cpu": float(cpu_str) if cpu_str else 0.0,
                        "mem": float(mem_str) if mem_str else 0.0,
                        "mem_usage": raw.get("MemUsage"),
                    })
                except (json.JSONDecodeError, ValueError) as e:
                    logger.debug(f"Skipping malformed stats line: {e}")
                    continue
    except subprocess.TimeoutExpired:
        logger.error("Docker stats timed out (30s)")
    except subprocess.CalledProcessError as e:
        # Don't flood logs if docker is just busy
        global _last_docker_error_log
        now = time.time()
        if now - _last_docker_error_log > 60:
            logger.error(f"Docker stats failed (exit {e.returncode})")
            _last_docker_error_log = now
    except Exception as e:
        logger.error(f"Failed to get container stats: {e}")
    return container_stats

def append_history(system, containers):
    """Batch 6 T1: Append metrics to history CSV with rotation."""
    ts = system["timestamp"]
    new_lines = []
    
    # Pre-format lines for batch write
    new_lines.append(f"{ts},host,{system['cpu']},{system['mem']}\n")
    for c in containers:
        new_lines.append(f"{ts},{c['name']},{c['cpu']},{c['mem']}\n")
        
    header = "timestamp,name,cpu,mem\n"
    
    try:
        # Step 1: Ensure header and Append new data
        mode = 'a' if os.path.isfile(HISTORY_CSV) and os.path.getsize(HISTORY_CSV) > 0 else 'w'
        try:
            with open(HISTORY_CSV, mode) as f:
                if mode == 'w':
                    f.write(header)
                f.writelines(new_lines)
        except PermissionError:
            # Audit fix: don't crash if locked, just log and skip this cycle
            logger.warning("metrics-history.csv is currently locked. Skipping this history record.")
            return

        # Step 2: Periodic Rotation check (every 10 minutes)
        last_prune_file = os.path.join(STATE_DIR, "last_prune.json")
        last_prune_ts = 0
        try:
            if os.path.exists(last_prune_file):
                with open(last_prune_file, 'r') as pf:
                    last_prune_ts = json.loads(pf.read().strip() or '{}').get("ts", 0)
        except Exception as pe:
            logger.debug(f"Non-critical last_prune read failure: {pe}")

        if ts - last_prune_ts > 600:
            try:
                if os.path.exists(HISTORY_CSV):
                    with open(HISTORY_CSV, "r") as f:
                        # Use maxlen to automatically prune oldest line on read
                        all_lines = collections.deque(f, maxlen=MAX_HISTORY_ENTRIES)
                    
                    # Write to temp file then replace (Audit Fix 8)
                    tmp_csv = f"{HISTORY_CSV}.tmp"
                    with open(tmp_csv, "w") as f:
                        if all_lines and not all_lines[0].startswith("timestamp"):
                            f.write(header)
                        f.writelines(all_lines)
                    
                    safe_replace(tmp_csv, HISTORY_CSV)
                
                # Update last prune timestamp
                with open(last_prune_file, 'w') as pf:
                    json.dump({"ts": ts}, pf)
                logger.info("Rotated metrics-history.csv")
            except PermissionError:
                logger.warning("Rotation failed: metrics-history.csv is locked.")
            except Exception as e:
                logger.error(f"Rotation error: {e}")
    except Exception as e:
        logger.error(f"Failed to process history: {e}")

def collect_all_metrics():
    system = get_system_metrics()
    containers = get_container_metrics()
    
    data = {
        "system": system,
        "containers": containers,
        "timestamp": system["timestamp"]
    }
    
    if save_json(METRICS_JSON, data, caller="metrics"):
        append_history(system, containers)
        logger.info("Captured metrics and history.")

if __name__ == "__main__":
    wrap_agent("metrics", collect_all_metrics)
