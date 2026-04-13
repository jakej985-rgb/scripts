import requests
import os
import sys
import time
from .router import get_updates

# ANSI colors for nice UI
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
END = "\033[0m"

# M3TAL Telegram Auto-Discovery Engine
# Scans for #m3tal_ tags to map Chat IDs to names

def discover_and_map():
    """
    Polls getUpdates and maps #m3tal_ tags to Chat IDs.
    Returns: dict { 'TG_MAIN_CHAT_ID': cid, ... }
    """
    tags_info = {
        "#m3tal_main": "Main Notifications",
        "#m3tal_log": "System Logs",
        "#m3tal_error": "Error Alerts",
        "#m3tal_alert": "Critical Alerts",
        "#m3tal_action": "Command/Action Channel",
        "#m3tal_docker": "Docker Telemetry"
    }

    print(f"\n🔍 {BOLD}Telegram Auto-Discovery Mode{END}")
    print("M3TAL is looking for the following tags:")
    for tag, desc in tags_info.items():
        print(f"  {YELLOW}{tag:15}{END} -> {desc}")
    
    print(f"\n{BOLD}INSTRUCTIONS:{END}")
    print("1. Open your Telegram Bot.")
    print("2. Send the tags above to the chats you want to map.")
    input(f"3. {CYAN}Press Enter once you have sent the tags to start scanning...{END}")
    
    print(f"\n🚀 {BOLD}Scanning...{END}")
    
    mapping = {}
    found_tags = set()
    
    # Force a look at history
    url = f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN')}/getUpdates"
    
    for attempt in range(10): # 20 second window
        try:
            resp = requests.get(url, timeout=10).json()
            updates = resp.get("result", [])
            
            for update in updates:
                msg = update.get("message")
                if not msg or "text" not in msg:
                    continue
                
                text = msg["text"].lower()
                chat_id = msg["chat"]["id"]
                
                tags = {
                    "#m3tal_main": "TG_MAIN_CHAT_ID",
                    "#m3tal_log": "TG_LOG_CHAT_ID",
                    "#m3tal_error": "TG_ERROR_CHAT_ID",
                    "#m3tal_alert": "TG_ALERT_CHAT_ID",
                    "#m3tal_action": "TG_ACTION_CHAT_ID",
                    "#m3tal_docker": "TG_DOCKER_CHAT_ID"
                }
                
                for tag, env_key in tags.items():
                    if tag in text and env_key not in mapping:
                        mapping[env_key] = chat_id
                        if tag not in found_tags:
                            print(f"  ✅ {GREEN}Found {tag}{END} in chat {chat_id}")
                            found_tags.add(tag)
            
            if len(mapping) >= 1:
                # If we found something, pulse faster
                time.sleep(1)
            else:
                time.sleep(2)
                
            if attempt % 2 == 0:
                print(f"  ... polling ({attempt+1}/10)")
                
        except Exception as e:
            print(f"Discovery poll error: {e}")
            break
            
    return mapping
