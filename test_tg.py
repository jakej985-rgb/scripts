import os
import sys
import re
from pathlib import Path

# M3TAL Telegram Diagnostic Tool
# This script bypasses the orchestrator to test the bot connection directly.

def load_env(root: Path):
    env_file = root / ".env"
    if not env_file.exists():
        print(f"❌ .env not found at {env_file}")
        return
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

# Bootstrap
REPO_ROOT = Path(__file__).resolve().parent
CP_DIR = REPO_ROOT / "control-plane"
load_env(REPO_ROOT)

if str(CP_DIR) not in sys.path:
    sys.path.append(str(CP_DIR))

try:
    from agents import telegram
    from config.telegram import BOT_TOKEN, CHAT_COUNT
    
    # Safe printing for Windows
    token_len = len(BOT_TOKEN) if BOT_TOKEN else 0
    print(f"--- M3TAL Telegram Diagnostic ---")
    print(f"Token length: {token_len}")
    print(f"Chat count: {CHAT_COUNT}")
    print(f"Allowed users: {os.getenv('ALLOWED_USERS', 'Not Set')}")
    
    if token_len == 0:
        print("❌ ERROR: BOT_TOKEN is missing! Check your .env file.")
        sys.exit(1)

    print("Testing connection to Telegram API...")
    telegram.start()
    
    # Send a test message to main chat
    print("Sending test message...")
    # Avoid emojis in print for Windows console safety
    telegram.send_main("System Test: M3TAL Telegram subsystem is functional.")
    print("DONE! If you didn't receive a message, your BOT_TOKEN or CHAT_ID is likely wrong.")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
