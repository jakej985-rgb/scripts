import os
import json
import sys
from pathlib import Path

# --- Root Resolution (Phase 4 Hardening) --------------------------------------
# Automatically detect repo root by walking up parents until .env + docker/ are found.
def find_root():
    p = Path(__file__).resolve()
    # Walk up from the current file's location
    for parent in [p] + list(p.parents):
        if (parent / ".env").exists() and (parent / "docker").exists():
            return parent
    # Fallback to current working directory if it looks like the root
    cwd = Path.cwd()
    if (cwd / ".env").exists() and (cwd / "docker").exists():
        return cwd
    return None

REPO_ROOT = find_root()
if not REPO_ROOT:
    # We cannot function without a root anchor
    print("❌ FATAL: Could not locate M3TAL repository root (missing .env or docker/)")
    sys.exit(1)

# --- Environment Variable Keys ------------------------------------------------
ENV_TELEGRAM_TOKEN = "TELEGRAM_TOKEN"
ENV_TELEGRAM_CHAT  = "TELEGRAM_CHAT_ID"
ENV_REPO_ROOT      = "REPO_ROOT"

# --- Global Component Paths ---------------------------------------------------
CONTROL_PLANE = REPO_ROOT / "control-plane"
CORE_LOGS_DIR = CONTROL_PLANE / "state" / "logs"
AGENTS_DIR = CONTROL_PLANE / "agents"
DOCKER_DIR = REPO_ROOT / "docker"
DASHBOARD_DIR = REPO_ROOT / "dashboard"
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Script Subfolders
SCRIPTS_DEBUG = SCRIPTS_DIR / "debug"
SCRIPTS_HELPERS = SCRIPTS_DIR / "helpers"
SCRIPTS_CONFIG = SCRIPTS_DIR / "config"
SCRIPTS_TEST = SCRIPTS_DIR / "test"
SCRIPTS_MAINT = SCRIPTS_DIR / "maintenance"

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
TELEGRAM_OFFSET_TXT = STATE_DIR / "telegram_offset.txt"
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
    "command_listener": 2,
    "scaling": 2,
    "network_guard": 2,
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
    "scaling": [METRICS_JSON],
    "network_guard": [DOCKER_DIR],
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
