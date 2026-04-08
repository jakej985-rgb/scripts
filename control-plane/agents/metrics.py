import subprocess
import json
import sys
import os
import time

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR
from utils.state import save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("metrics")
METRICS_JSON = os.path.join(STATE_DIR, "metrics.json")

def get_cpu_usage():
    if sys.platform == "win32":
        # Windows fallback for development
        cmd = "wmic cpu get loadpercentage /value"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        for line in res.stdout.splitlines():
            if "LoadPercentage" in line:
                return float(line.split('=')[1])
        return 0.0
    else:
        # Linux standard
        cpu_cmd = "grep 'cpu ' /proc/stat | awk '{print ($2+$4)*100/($2+$4+$5)}'"
        result = subprocess.run(cpu_cmd, shell=True, capture_output=True, text=True)
        return float(result.stdout.strip()) if result.stdout.strip() else 0.0

def collect_metrics():
    """Collect system-level metrics as per Task 3."""
    cpu = get_cpu_usage()
    
    # Simple metrics for now
    data = {
        "cpu": round(cpu, 2),
        "timestamp": int(time.time()),
        "load_status": "nominal" if cpu < 80 else "high"
    }
    
    save_json(METRICS_JSON, data)
    logger.info(f"System metrics captured: CPU {cpu}%")

if __name__ == "__main__":
    wrap_agent("metrics", collect_metrics)
