import os
import re
from pathlib import Path
from typing import Dict

def load_env(repo_root: Path) -> Dict[str, str]:
    """Load .env file into a dictionary for subprocess propagation.
    
    NOTE: This function also sets values into os.environ as a side effect
    so that subprocesses and modules using os.getenv() see the loaded values.
    """
    env = os.environ.copy()
    env_path = repo_root / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    # Only strip inline comments preceded by whitespace (preserve # in values)
                    v = re.sub(r'\s+#.*$', '', v).strip()
                    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                        v = v[1:-1]
                    env[k.strip()] = v
                    os.environ[k.strip()] = v
    # Force REPO_ROOT for Docker
    env["REPO_ROOT"] = str(repo_root)
    os.environ["REPO_ROOT"] = str(repo_root)
    return env
