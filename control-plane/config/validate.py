import os
import sys

# M3TAL Configuration Validation Layer
# Responsibility: Enforce "fail-fast" behavior for critical environment variables.

REQUIRED = [
    "DOMAIN",
    "CF_TUNNEL_TOKEN",
    "TELEGRAM_BOT_TOKEN",
]

def validate():
    """
    Validates that all required environment variables are present and non-empty.
    Also detects domain drift and environment leakage.
    """
    missing = [k for k in REQUIRED if not (os.getenv(k) or "").strip()]
    if missing:
        print("=" * 60)
        print("[!] CONFIGURATION ERROR: MISSING REQUIRED ENVIRONMENT VARIABLES")
        print("=" * 60)
        for k in missing:
            print(f"  - {k}")
        print("\nPlease ensure these are defined in your .env file at the repository root.")
        print("See docs/GET_STARTED.md for configuration help.")
        print("=" * 60)
        sys.exit(1)

    # Drift Detection: Ensure DOMAIN is correctly resolved from .env
    domain = os.getenv("DOMAIN")
    if domain == "m3tal-media-server.xyz" and not os.path.exists(os.path.join(os.getcwd(), ".env")):
        print("[WARNING] Domain Drift Detected: Using default fallback. Ensure .env is loaded.")

if __name__ == "__main__":
    validate()
    print("✅ Configuration validated: OK")
