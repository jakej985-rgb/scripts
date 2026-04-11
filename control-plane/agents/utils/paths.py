import os
import json
from pathlib import Path

# --- Root Resolution ----------------------------------------------------------
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
RESTARTS_JSON = STATE_DIR / "restarts.json"
ANOMALIES_JSON = STATE_DIR / "anomalies.json"
DECISIONS_JSON = STATE_DIR / "decisions.json"
REGISTRY_JSON = STATE_DIR / "registry.json"
HEALTH_REPORT_JSON = STATE_DIR / "health_report.json"
NORMALIZED_METRICS_JSON = STATE_DIR / "normalized_metrics.json"
COOLDOWNS_JSON = STATE_DIR / "cooldowns.json"
CLUSTER_YML = CONFIG_DIR / "cluster.yml"

# --- Agent Tier & Contract Registry -------------------------------------------
# Tier 1: System-critical. Hard fail on contract breach.
# Tier 2: Edge/Feature. Degrade on contract breach.
TIERS = {
    "leader": 1,
    "registry": 1,
    "monitor": 1,
    "decision": 1,
    "reconcile": 1,
    "metrics": 2,
    "anomaly": 2,
    "health_score": 1, # Health score is critical for notify/decision logic
    "notify": 2,
    "observer": 2,
    "tunnel": 2,
    "healer": 2,
}

# The absolute minimum files/dirs required for each agent to start
CONTRACTS = {
    "leader": [CLUSTER_YML],
    "registry": [DOCKER_DIR],
    "monitor": [REGISTRY_JSON],
    "metrics": [REGISTRY_JSON],
    "anomaly": [CONTAINER_HEALTH_JSON, METRICS_JSON],
    "decision": [ANOMALIES_JSON], # COOLDOWNS is internal, will be created
    "reconcile": [DECISIONS_JSON, REGISTRY_JSON],
    "health_score": [METRICS_JSON, CONTAINER_HEALTH_JSON],
    "notify": [HEALTH_REPORT_JSON],
}

def ensure_dirs():
    """Safety: ensure all core state/log directories exist."""
    dirs = [STATE_DIR, LOG_DIR, LOCK_DIR, HEALTH_DIR, CONFIG_DIR]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

def validate_contract(agent_name: str) -> tuple[bool, str]:
    """Startup check for agent contract integrity.
    Returns (success, error_message).
    """
    required_paths = CONTRACTS.get(agent_name, [])
    tier = TIERS.get(agent_name, 2)
    
    missing = []
    for p in required_paths:
        path = Path(p)
        if not path.exists():
            missing.append(path.name)
        elif path.suffix == ".json":
            # Basic integrity check for JSON files
            from .state import validate_state
            if not validate_state(str(path), expected_type=(dict, list)):
                missing.append(f"{path.name} (corrupt)")
                
    if missing:
        mode = "HARD_FAIL" if tier == 1 else "DEGRADED"
        return False, f"Contract breached: missing {', '.join(missing)} [{mode}]"
        
    return True, ""

if __name__ == "__main__":
    print(f"M3TAL Path Standard: {REPO_ROOT}")
    ensure_dirs()
