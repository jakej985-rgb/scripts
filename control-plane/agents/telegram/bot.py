"""
M3TAL Telegram Bot Runtime (v3.2)
Responsibility: Combines the background worker and the command listener.
Launched by: control-plane/run.py
"""

import time
import sys
import os
from . import service as tg_service
from . import router
from . import logger

# Add agents dir to path to find command_listener logic if needed
# or we can just import the logic here.
from agents.command_listener import handle_command

def run_bot():
    """
    Primary bot runtime loop.
    Starts the worker thread and polls for new commands.
    """
    print("[TELEGRAM] Starting Bot Runtime (Worker + Listener)...")
    
    # 1. Start Worker (Non-blocking thread)
    tg_service.start()
    
    # 2. Command Listener Loop
    offset = 0
    try:
        # Initialize offset to latest to avoid flood on startup
        updates = router.get_new_updates(offset=0)
        if updates:
            offset = updates[-1]["update_id"]
            print(f"[TELEGRAM] Offset initialized to {offset}")
    except Exception as e:
        print(f"[TELEGRAM] Initialization error: {e}")

    # Use a logger to signal startup
    logger.log("M3TAL Bot Runtime started.")

    while True:
        try:
            updates = router.get_new_updates(offset=offset)
            for update in updates:
                handle_command(update)
                offset = update["update_id"]
            
            time.sleep(2)
        except Exception as e:
            print(f"[TELEGRAM] Runtime Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # If run standalone for some reason
    run_bot()
