import json
import os
import time
from typing import Any

SCHEMA_VERSION = "1.3.0"

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

def save_json(path: str, data: Any) -> bool:
    """Atomic write to JSON file with schema metadata injection (Batch 8 T5)"""
    tmp_path = f"{path}.tmp"
    
    # Inject metadata if data is a dict (Audit fix 2.12 - use safe copy)
    if isinstance(data, dict):
        data = data.copy()
        data["_m3tal_metadata"] = {
            "version": SCHEMA_VERSION,
            "updated_at": int(time.time()),
            "host": os.getenv("HOSTNAME", "localhost")
        }

    try:
        # Create directory if it doesn't exist (Audit fix 2.8: handle bare files)
        parent = Path(path).parent
        if str(parent) not in (".", ""):
            parent.mkdir(parents=True, exist_ok=True)
        
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            # Ensure it's flushed to disk before move
            f.flush()
            os.fsync(f.fileno())
            
        os.replace(tmp_path, path)
        return True
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except:
                pass
        return False

def validate_state(path: str, expected_type: type = list) -> bool:
    """Check if file exists and contains the expected data type"""
    data = load_json(path)
    return isinstance(data, expected_type)
