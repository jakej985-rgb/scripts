import os

# Root resolution
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Control Plane paths
STATE_DIR = os.path.join(BASE_DIR, "control-plane", "state")
LOGS_DIR = os.path.join(STATE_DIR, "logs")
CONFIG_DIR = os.path.join(BASE_DIR, "control-plane", "config")

# State Files
METRICS_JSON = os.path.join(STATE_DIR, "metrics.json")
NORMALIZED_METRICS_JSON = os.path.join(STATE_DIR, "normalized_metrics.json")
ANOMALIES_JSON = os.path.join(STATE_DIR, "anomalies.json")
DECISIONS_JSON = os.path.join(STATE_DIR, "decisions.json")
CLUSTER_YML = os.path.join(CONFIG_DIR, "cluster.yml")
TRAEFIK_DYNAMIC_YML = os.path.join(STATE_DIR, "traefik-dynamic.yml")

def ensure_dirs():
    for d in [STATE_DIR, LOGS_DIR, CONFIG_DIR]:
        os.makedirs(d, exist_ok=True)
