import requests
import os
import sys
import time
from .router import get_updates

from config.telegram import BOT_TOKEN

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
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    attempt = 0
    max_attempts = 15
    
    while attempt < max_attempts:
        attempt += 1
        try:
            resp_raw = requests.get(url, timeout=10)
            if resp_raw.status_code == 401:
                print(f"  ❌ {RED}ERROR: Invalid Bot Token (401 Unauthorized).{END}")
                print(f"     Check your token: {BOT_TOKEN[:10]}...")
                return mapping
            elif resp_raw.status_code != 200:
                print(f"  ❌ {RED}ERROR: Telegram API returned {resp_raw.status_code}{END}")
                print(f"     Details: {resp_raw.text}")
                return mapping

            resp = resp_raw.json()
            if not resp.get("ok"):
                print(f"  ❌ {RED}ERROR: Telegram reports failure.{END}")
                print(f"     Message: {resp.get('description', 'Unknown error')}")
                return mapping

            updates = resp.get("result", [])
            update_count = len(updates)
            
            if update_count > 0:
                print(f"  📥 {CYAN}Received {update_count} messages, checking for tags...{END}")
            
            new_discovery_this_poll = False
            for update in updates:
                msg = update.get("message")
                if not msg or "text" not in msg:
                    continue
                
                text = msg["text"].lower()
                chat_id = msg["chat"]["id"]
                
                found_any_tag_in_msg = False
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
                        found_any_tag_in_msg = True
                        if tag not in found_tags:
                            print(f"  ✅ {GREEN}Found {tag}{END} in chat {chat_id}")
                            found_tags.add(tag)
                            new_discovery_this_poll = True
                
                if not found_any_tag_in_msg and update_count > 0 and attempt % 3 == 0:
                    print(f"  💡 {YELLOW}Heard from chat {chat_id}, but no #m3tal_ tags detected.{END}")
            
            if new_discovery_this_poll:
                print(f"  🔄 {BOLD}{CYAN}Discovery reset!{END} Giving you {max_attempts} more tries to find the rest...")
                attempt = 0

            if len(found_tags) >= len(tags_info):
                print(f"\n{GREEN}✨ All tags discovered! Success.{END}")
                break

            if attempt % 1 == 0:  # Show on every attempt
                missing_names = [name for env, tag, name in [
                    ("TG_MAIN_CHAT_ID", "#m3tal_main", "Main"),
                    ("TG_LOG_CHAT_ID", "#m3tal_log", "Logs"),
                    ("TG_ERROR_CHAT_ID", "#m3tal_error", "Error"),
                    ("TG_ALERT_CHAT_ID", "#m3tal_alert", "Alert"),
                    ("TG_ACTION_CHAT_ID", "#m3tal_action", "Action"),
                    ("TG_DOCKER_CHAT_ID", "#m3tal_docker", "Docker")
                ] if env not in mapping]
                
                from datetime import datetime
                ts = datetime.now().strftime("%H:%M:%S")
                missing_str = ", ".join(missing_names)
                print(f"  [{ts}] ⏳ {YELLOW}Attempt {attempt}/{max_attempts}:{END} Waiting for {BOLD}[{missing_str}]{END}... ({len(found_tags)}/6 found)")

            if len(mapping) >= 1:
                time.sleep(1.5)
            else:
                time.sleep(2.5)
                
        except Exception as e:
            print(f"Discovery poll error: {e}")
            break
            
    return mapping
