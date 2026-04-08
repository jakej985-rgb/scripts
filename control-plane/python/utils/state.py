import json
import os
import shutil

def load_json(path, default=None):
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default

def save_json(path, data):
    """Atomic write to JSON file"""
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, 'w') as f:
            json.dump(data, f, indent=4)
        os.replace(tmp_path, path)
        return True
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        print(f"Error saving JSON to {path}: {e}")
        return False

def append_json_line(path, data):
    """For files like anomalies.json that might be line-delimited or raw sequences"""
    try:
        with open(path, 'a') as f:
            f.write(json.dumps(data) + "\n")
        return True
    except Exception:
        return False
