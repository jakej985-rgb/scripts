import os

# Root resolution
# Since this lives in control-plane/agents/utils/, we need to go up 3 levels to reach GitHub/M3tal-Media-Server/
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
REPO_ROOT = BASE_DIR

# Control Plane paths
STATE_DIR = os.path.join(BASE_DIR, "control-plane", "state")
LOG_DIR = os.path.join(STATE_DIR, "logs")
CONFIG_DIR = os.path.join(BASE_DIR, "control-plane", "config")
DOCKER_DIR = os.path.join(BASE_DIR, "docker")

# State Files (Standardized via AGENT_PLAN.md)
LEADER_TXT = os.path.join(STATE_DIR, "leader.txt")
HEALTH_JSON = os.path.join(STATE_DIR, "health.json")
CONTAINER_HEALTH_JSON = os.path.join(STATE_DIR, "health", "monitor_containers.json")
METRICS_JSON = os.path.join(STATE_DIR, "metrics.json")
ANOMALIES_JSON = os.path.join(STATE_DIR, "anomalies.json")
DECISIONS_JSON = os.path.join(STATE_DIR, "decisions.json")
REGISTRY_JSON = os.path.join(STATE_DIR, "registry.json")
COOLDOWNS_JSON = os.path.join(STATE_DIR, "cooldowns.json")
NORMALIZED_METRICS_JSON = os.path.join(STATE_DIR, "normalized_metrics.json")
HEALTH_REPORT_JSON = os.path.join(STATE_DIR, "health_report.json")

# Config Files
CLUSTER_YML = os.path.join(CONFIG_DIR, "cluster.yml")
JOBS_JSON = os.path.join(CONFIG_DIR, "jobs.json")
NODES_JSON = os.path.join(CONFIG_DIR, "nodes.json")

# Extra paths
TRAEFIK_DYNAMIC_YML = os.path.join(STATE_DIR, "traefik-dynamic.yml")

def ensure_dirs():
    for d in [STATE_DIR, LOG_DIR, CONFIG_DIR]:
        os.makedirs(d, exist_ok=True)
