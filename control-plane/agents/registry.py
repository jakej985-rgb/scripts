import sys
import os
import subprocess
import yaml

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import CLUSTER_YML, TRAEFIK_DYNAMIC_YML
from utils.state import save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("registry")

def update_routing():
    if not os.path.exists(CLUSTER_YML):
        logger.error("Registry missing cluster.yml. Skipping update.")
        return

    with open(CLUSTER_YML, 'r') as f:
        cluster = yaml.safe_load(f) or {}
        
    services = cluster.get('services', {})
    nodes = cluster.get('nodes', {})
    dynamic_config = {"http": {"services": {}, "routers": {}}}
    
    for svc_name, svc_info in services.items():
        port = svc_info.get('port')
        if not port: continue
            
        servers = []
        for node_name, node_info in nodes.items():
            host = node_info.get('host', 'localhost')
            try:
                # Basic check for running container
                target_cmd = ["docker", "ps", "--filter", f"name={svc_name}", "--format", "{{.Names}}"]
                if host == "localhost":
                    res = subprocess.run(target_cmd, capture_output=True, text=True, check=True)
                else:
                    res = subprocess.run(["ssh", "-o", "ConnectTimeout=2", host] + target_cmd, capture_output=True, text=True, check=True)
                
                if res.stdout.strip():
                    target = host.split('@')[-1].split(':')[0]
                    if target == "localhost": target = "127.0.0.1"
                    servers.append({"url": f"http://{target}:{port}"})
            except Exception:
                continue
        
        if servers:
            dynamic_config["http"]["services"][svc_name] = {
                "loadBalancer": {"servers": servers, "healthCheck": {"interval": "10s", "path": "/"}}
            }
            dynamic_config["http"]["routers"][svc_name] = {
                "rule": f"Host(`{svc_name}.local`)", "service": svc_name, "entryPoints": ["web"]
            }
            
    tmp_path = f"{TRAEFIK_DYNAMIC_YML}.tmp"
    with open(tmp_path, 'w') as f:
        yaml.dump(dynamic_config, f, default_flow_style=False)
    os.replace(tmp_path, TRAEFIK_DYNAMIC_YML)

if __name__ == "__main__":
    wrap_agent("registry", update_routing)
