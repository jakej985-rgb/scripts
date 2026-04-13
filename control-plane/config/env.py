import os
from pathlib import Path
from dotenv import load_dotenv

# Define root paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOTENV_PATH = REPO_ROOT / ".env"

# Load .env if it exists
if DOTENV_PATH.exists():
    load_dotenv(str(DOTENV_PATH))

REQUIRED_VARS = [
    "REPO_ROOT",
    "DATA_DIR",
    "CONFIG_DIR",
    "DOMAIN",
]

def validate_env():
    """Validate that all required environment variables are present."""
    # Ensure REPO_ROOT is correctly set if missing (default to dynamic resolution)
    if not os.getenv("REPO_ROOT"):
        os.environ["REPO_ROOT"] = str(REPO_ROOT)
        
    missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
    if missing:
        error_msg = f"Missing required environment variables: {', '.join(missing)}\n"
        error_msg += f"Please ensure these are defined in {DOTENV_PATH}"
        raise RuntimeError(error_msg)
    
    # Standardize paths to absolute
    for var in ["REPO_ROOT", "DATA_DIR", "CONFIG_DIR"]:
        val = os.getenv(var)
        if val:
            os.environ[var] = str(Path(val).resolve())

if __name__ == "__main__":
    try:
        validate_env()
        print("✅ Environment validation successful.")
        for var in REQUIRED_VARS:
            print(f"  {var} = {os.getenv(var)}")
    except RuntimeError as e:
        print(f"❌ {e}")
        exit(1)
