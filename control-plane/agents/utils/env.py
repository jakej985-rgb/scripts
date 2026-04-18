import os
from pathlib import Path
from typing import Dict

def load_env(repo_root: Path) -> Dict[str, str]:
    """Surgically load .env file into a dictionary for subprocess propagation."""
    env = os.environ.copy()
    env_path = repo_root / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    # Strip inline comments, whitespace, and quotes
                    v = v.split("#")[0].strip()
                    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                        v = v[1:-1]
                    env[k.strip()] = v
                    os.environ[k.strip()] = v
    # Force REPO_ROOT for Docker
    env["REPO_ROOT"] = str(repo_root)
    os.environ["REPO_ROOT"] = str(repo_root)
    return env
