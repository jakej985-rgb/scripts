import sys
import os
import socket

# Add current dir to path for utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import CLUSTER_YML, LEADER_TXT
from utils.identity import get_local_identity, is_local_host, normalize_host_identifier
from utils.logger import get_logger

logger = get_logger("leader")

def get_node_identity():
    try:
        # Use hostname + local IP for a better unique ID than just 'localhost'
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return f"{hostname}@{ip}"
    except:
        return socket.gethostname()

def elect_leader():
    """Phase 1: Python Leader Election as per Audit Batch 4 T1."""
    # In a real Raft, we'd have term numbers. Here we use an order-based priority
    # from the cluster.yml node list.
    
    try:
        import yaml
        with open(CLUSTER_YML, 'r') as f:
            cluster_config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to read cluster.yml: {e}")
        return

    nodes = cluster_config.get("nodes", {})
    control_nodes = [name for name, cfg in nodes.items() if cfg.get("role") == "control"]
    
    if not control_nodes:
        logger.warning("No control nodes defined in cluster.yml. Defaulting to self.")
        with open(LEADER_TXT, "w") as f:
            f.write(socket.gethostname())
        return

    my_id = get_node_identity()
    my_identity = get_local_identity()

    # Priority order: first node in list is primary
    primary_node = control_nodes[0]
    primary_cfg = nodes[primary_node]
    primary_host = primary_cfg.get("host", "")
    primary_identity = normalize_host_identifier(primary_host)

    # Check if primary is reachable or is US
    is_primary_up = False
    if is_local_host(primary_identity):
        is_primary_up = True
        leader_identity = my_identity
    else:
        # Ping check for remote primary
        try:
            # Simple socket connect to test reachability
            socket.create_connection((primary_identity, 22), timeout=1).close()
            is_primary_up = True
        except:
            is_primary_up = False

        leader_identity = primary_identity if is_primary_up else my_identity

    with open(LEADER_TXT, "w") as f:
        f.write(leader_identity)

    if is_local_host(leader_identity):
        logger.info(f"Identity: {my_id} | STATUS: [LEADER]")
        sys.exit(0) # Success code for run_agent to continue
    else:
        logger.info(f"Identity: {my_id} | STATUS: [FOLLOWER] (Leader: {leader_identity})")
        sys.exit(1) # Error code for run_agent to sleep/skip

if __name__ == "__main__":
    elect_leader()
