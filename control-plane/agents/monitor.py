import subprocess
import json
import sys
import os

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import METRICS_JSON
from utils.state import save_json
from utils.logger import get_logger

logger = get_logger("monitor")

def collect_container_data():
    try:
        logger.info("Collecting raw container data...")
        cmd = ["docker", "ps", "-a", "--format", "{{json .}}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # docker ps --format {{json .}} outputs one JSON object per line
        containers = []
        for line in result.stdout.strip().split('\n'):
            if line:
                containers.append(json.loads(line))
        
        if save_json(METRICS_JSON, containers):
            logger.info(f"Successfully saved {len(containers)} container states to {METRICS_JSON}")
        else:
            logger.error("Failed to save container data")
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Docker command failed: {e.stderr}")
    except Exception as e:
        logger.error(f"Unexpected error in monitor: {e}")

if __name__ == "__main__":
    collect_container_data()
