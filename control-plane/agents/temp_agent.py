import os
import sys
import time
import subprocess

try:
    import psutil
except ImportError:
    psutil = None

# Standardize path resolution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.paths import TEMP_JSON
from utils.state import save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("temp_agent")

def get_cpu_temp():
    if not psutil:
        return None
    try:
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if not temps:
                return None
            
            # Common coretemp names
            for name in ["coretemp", "k10temp", "acpitz"]:
                if name in temps:
                    for entry in temps[name]:
                        return entry.current
            
            # Fallback to first available sensor
            for name, entries in temps.items():
                if entries:
                    return entries[0].current
    except Exception as e:
        logger.debug(f"psutil.sensors_temperatures() failed: {e}")
    return None

def get_gpu_temp():
    try:
        # Check nvidia-smi
        cmd = ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            lines = res.stdout.strip().split("\n")
            if lines and lines[0].isdigit():
                return float(lines[0])
    except Exception:
        pass
    return None

def read_thermal_zone():
    """Fallback for Linux host reading /sys/class/thermal directly."""
    try:
        zone_path = "/sys/class/thermal/thermal_zone0/temp"
        if os.path.exists(zone_path):
            with open(zone_path, "r") as f:
                temp_milli = int(f.read().strip())
                return float(temp_milli) / 1000.0
    except Exception as e:
        logger.debug(f"thermal_zone read failed: {e}")
    return None

def collect_temps():
    logger.info("[TEMP] Collecting temperature metrics...")
    
    cpu = get_cpu_temp()
    if cpu is None:
        cpu = read_thermal_zone()

    gpu = get_gpu_temp()

    # Graceful degradation for local Windows dev
    if cpu is None and sys.platform == "win32":
        logger.info("[TEMP] Simulating temperatures on Windows dev machine.")
        # We can just leave them as None, frontend handles N/A

    data = {
        "cpu_temp": cpu,
        "gpu_temp": gpu,
        "timestamp": int(time.time()),
        "status": "healthy"
    }

    # Evaluate Thresholds
    max_temp = max(t for t in [cpu, gpu] if t is not None) if (cpu is not None or gpu is not None) else 0

    if max_temp >= 85:
        data["status"] = "critical"
        logger.warning(f"[TEMP] CRITICAL Temperature detected: {max_temp}°C")
    elif max_temp >= 75:
        data["status"] = "warning"
        logger.info(f"[TEMP] Warning Temperature detected: {max_temp}°C")

    save_json(TEMP_JSON, data, caller="temp_agent")
    logger.info(f"[TEMP] Saved metrics. CPU: {cpu}°C, GPU: {gpu}°C")

if __name__ == "__main__":
    wrap_agent("temp_agent", collect_temps)
