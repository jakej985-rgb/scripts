import json
import os
import time
import errno
import shutil
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.3.0"

# --- File Ownership Registry --------------------------------------------------
# This map defines which agent 'owns' (is allowed to write) which state file.
# Used to detect and log concurrent write violations.
OWNERS = {
    "registry.json": "registry",
    "monitor_containers.json": "monitor",
    "metrics.json": "metrics",
    "normalized_metrics.json": "metrics",
    "anomalies.json": "anomaly",
    "decisions.json": "decision",
    "cooldowns.json": "decision",
    "health_report.json": "health_score",
    "notify_state.json": "notify",
    "scaling_actions.json": "scaling",
    "scaling_cooldowns.json": "scaling",
    "chaos_events.json": "anomaly",
    "network_guard_state.json": "network_guard",
    "observer_seen.json": "observer",
    "restarts.json": "run", # Managed by orchestrator
}

def load_json(path: str, default: Any = None) -> Any:
    """Safe JSON load with robust fallback and type consistency check"""
    if default is None:
        default = {}
    
    if not os.path.exists(path):
        return default
        
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return default
            data = json.loads(content)
            
            # Audit fix 2.12: Enforce type consistency with default
            if default is not None and type(data) != type(default):
                return default
                
            return data
    except (json.JSONDecodeError, IOError, UnicodeDecodeError):
        # If corrupted, return default rather than crash
        return default

def safe_replace(src: str, dst: str):
    """Atomic replace with fallback for cross-device renames (Docker volumes)"""
    try:
        os.replace(src, dst)
    except OSError as e:
        # Cross-device move (errno 18: EXDEV) or other atomic failure
        if e.errno == errno.EXDEV or os.name == 'nt':
            shutil.copy2(src, dst)
            try: os.remove(src)
            except Exception: pass
        else:
            raise

def save_json(path: str, data: Any, caller: str = "unknown") -> bool:
    """Production-grade atomic write to JSON file.
    Pattern: tempfile -> fsync -> safe_replace.
    Includes ownership validation and detailed error logging.
    """
    path_obj = Path(path)
    filename = path_obj.name
    
    # 1. Ownership Validation
    expected_owner = OWNERS.get(filename)
    if expected_owner and caller != "unknown" and caller != expected_owner:
        from .logger import get_logger
        get_logger("state").warning(f"OWNERSHIP_VIOLATION: Agent '{caller}' is writing to '{filename}' (Owned by '{expected_owner}')")

    tmp_path = f"{path}.tmp"
    
    if isinstance(data, dict):
        data = data.copy()
        data["_m3tal_metadata"] = {
            "version": SCHEMA_VERSION,
            "updated_at": int(time.time()),
            "host": os.getenv("HOSTNAME", "localhost"),
            "writer": caller
        }

    try:
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
            
        safe_replace(tmp_path, path)
        return True
    except Exception as e:
        from .logger import get_logger
        err_msg = f"Failed to save {filename}"
        if hasattr(e, 'errno'):
            err_msg += f" [errno {e.errno}: {os.strerror(e.errno)}]"
        
        get_logger("state").error(f"{err_msg}: {e} (Path: {os.path.abspath(path)})")
        
        if os.path.exists(tmp_path):
            try: os.remove(tmp_path)
            except Exception: pass
        return False

def validate_state(path: str, expected_type: type = list) -> bool:
    """Check if file exists and contains valid, non-corrupted data of expected type."""
    if not os.path.exists(path):
        return False
    try:
        data = load_json(path)
        return isinstance(data, expected_type)

    except Exception:
        return False
