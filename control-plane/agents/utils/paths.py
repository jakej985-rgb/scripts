import os
from pathlib import Path

# --- Root Resolution ----------------------------------------------------------
# If REPO_ROOT is provided in environment (Docker mode), use it.
# Otherwise, resolve it relative to this file (Dev mode).
env_root = os.getenv("REPO_ROOT")
if env_root:
    REPO_ROOT = Path(env_root)
else:
    # This file is at control-plane/agents/utils/paths.py
    REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# --- Global Component Paths ---------------------------------------------------
CONTROL_PLANE = REPO_ROOT / "control-plane"
AGENTS_DIR = CONTROL_PLANE / "agents"
DOCKER_DIR = REPO_ROOT / "docker"
DASHBOARD_DIR = REPO_ROOT / "dashboard"
SCRIPTS_DIR = REPO_ROOT / "scripts"

# --- State & Monitoring -------------------------------------------------------
STATE_DIR = CONTROL_PLANE / "state"
LOG_DIR = STATE_DIR / "logs"
LOCK_DIR = STATE_DIR / "locks"
HEALTH_DIR = STATE_DIR / "health"
CONFIG_DIR = CONTROL_PLANE / "config"

# --- Static State Files -------------------------------------------------------
LEADER_TXT = STATE_DIR / "leader.txt"
HEALTH_JSON = STATE_DIR / "health.json"
CONTAINER_HEALTH_JSON = HEALTH_DIR / "monitor_containers.json"
METRICS_JSON = STATE_DIR / "metrics.json"
RESTARTS_JSON = STATE_DIR / "restarts.json" # New: Track crash loops
ANOMALIES_JSON = STATE_DIR / "anomalies.json"
DECISIONS_JSON = STATE_DIR / "decisions.json"
REGISTRY_JSON = STATE_DIR / "registry.json"
HEALTH_REPORT_JSON = STATE_DIR / "health_report.json"
NORMALIZED_METRICS_JSON = STATE_DIR / "normalized_metrics.json"
COOLDOWNS_JSON = STATE_DIR / "cooldowns.json"
CLUSTER_YML = CONFIG_DIR / "cluster.yml"

# --- Dynamic Assets -----------------------------------------------------------
TRAEFIK_DYNAMIC_YML = STATE_DIR / "traefik-dynamic.yml"
THEME_JSON = STATE_DIR / "theme.json"

def ensure_dirs():
    """Safety: ensure all core state/log directories exist."""
    dirs = [STATE_DIR, LOG_DIR, LOCK_DIR, HEALTH_DIR, CONFIG_DIR]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

if __name__ == "__main__":
    print(f"M3TAL Path Standard: {REPO_ROOT}")
    ensure_dirs()
