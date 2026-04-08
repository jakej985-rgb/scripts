import subprocess
import json
import sys
import os

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import METRICS_JSON
from utils.state import save_json
from utils.guards import wrap_agent

def collect_container_data():
    cmd = ["docker", "ps", "-a", "--format", "{{json .}}"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    containers = []
    for line in result.stdout.strip().split('\n'):
        if line:
            containers.append(json.loads(line))
    
    # Rule #4: FAIL CLOSED - if no containers, we write empty list rather than fail
    save_json(METRICS_JSON, containers)

if __name__ == "__main__":
    wrap_agent("monitor", collect_container_data)
