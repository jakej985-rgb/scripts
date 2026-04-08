import sys
import os
import subprocess
import yaml

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import CLUSTER_YML, TRAEFIK_DYNAMIC_YML
from utils.state import save_json
from utils.logger import get_logger

logger = get_logger("registry")

def get_running_containers(host, svc):
    try:
        if host == "localhost":
            cmd = ["docker", "ps", "--format", "{{.Names}}"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        else:
            cmd = ["ssh", "-o", "ConnectTimeout=2", host, "docker ps --format '{{.Names}}'"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
        containers = result.stdout.strip().split('\n')
        return [c for c in containers if c.startswith(svc)]
    except Exception:
        return []

def update_routing():
    try:
        if not os.path.exists(CLUSTER_YML):
            return

        with open(CLUSTER_YML, 'r') as f:
            cluster = yaml.safe_load(f)
            
        services = cluster.get('services', {})
        nodes = cluster.get('nodes', {})
        
        dynamic_config = {
            "http": {
                "services": {},
                "routers": {}
            }
        }
        
        for svc_name, svc_info in services.items():
            port = svc_info.get('port')
            if not port:
                continue
                
            servers = []
            for node_name, node_info in nodes.items():
                host = node_info.get('host', 'localhost')
                running = get_running_containers(host, svc_name)
                
                if running:
                    target = host.split('@')[-1].split(':')[0]
                    if target == "localhost": target = "127.0.0.1"
                    
                    for _ in running:
                        servers.append({"url": f"http://{target}:{port}"})
            
            if servers:
                # Add Traefik Service
                dynamic_config["http"]["services"][svc_name] = {
                    "loadBalancer": {
                        "servers": servers,
                        "healthCheck": {
                            "interval": "10s",
                            "timeout": "5s",
                            "path": "/"
                        }
                    }
                }
                
                # Add Traefik Router
                dynamic_config["http"]["routers"][svc_name] = {
                    "rule": f"Host(`{svc_name}.local`)",
                    "service": svc_name,
                    "entryPoints": ["web"]
                }
                
        # Write YAML dynamic config for Traefik
        tmp_path = f"{TRAEFIK_DYNAMIC_YML}.tmp"
        with open(tmp_path, 'w') as f:
            yaml.dump(dynamic_config, f, default_flow_style=False)
        os.replace(tmp_path, TRAEFIK_DYNAMIC_YML)
        
        logger.info(f"Updated Traefik routing with {len(dynamic_config['http']['services'])} active services")
        
    except Exception as e:
        logger.error(f"Registry update failed: {e}")

if __name__ == "__main__":
    update_routing()
