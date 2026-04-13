import requests
import os
import sys
import time

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
    Polls getUpdates and maps simplified tags to Chat IDs.
    Returns: dict { 'TG_MAIN_CHAT_ID': cid, ... }
    """
    tags_info = {
        "#main": "Main Notifications",
        "#logs": "System Logs",
        "#error": "Error Alerts",
        "#alert": "Critical Alerts",
        "#action": "Command/Action Channel",
        "#docker": "Docker Telemetry"
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
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    attempt = 0
    max_attempts = 15
    
    while attempt < max_attempts:
        attempt += 1
        try:
            resp_raw = requests.get(url, timeout=10)
            if resp_raw.status_code != 200:
                print(f"  ❌ {RED}ERROR: API returned {resp_raw.status_code}{END}")
                return mapping

            resp = resp_raw.json()
            updates = resp.get("result", [])
            update_count = len(updates)
            
            if update_count > 0:
                print(f"  📥 {CYAN}Received {update_count} messages, checking...{END}")
            
            new_discovery = False
            for update in updates:
                msg = update.get("message") or update.get("channel_post")
                if not msg: continue
                
                text = (msg.get("text") or msg.get("caption") or "").lower().strip()
                chat_id = msg["chat"]["id"]
                
                # Debug: Print what we see (only if it looks like a tag)
                if text.startswith("#"):
                    print(f"    Saw: [ {text} ] in chat {chat_id}")

                tags = {
                    "#main": "TG_MAIN_CHAT_ID",
                    "#logs": "TG_LOG_CHAT_ID",
                    "#error": "TG_ERROR_CHAT_ID",
                    "#alert": "TG_ALERT_CHAT_ID",
                    "#action": "TG_ACTION_CHAT_ID",
                    "#docker": "TG_DOCKER_CHAT_ID"
                }
                
                for tag, env_key in tags.items():
                    if tag in text and env_key not in mapping:
                        mapping[env_key] = chat_id
                        if tag not in found_tags:
                            print(f"  ✅ {GREEN}Mapped {tag}{END} to {chat_id}")
                            found_tags.add(tag)
                            new_discovery = True
            
            if new_discovery:
                attempt = 0 

            if len(found_tags) >= len(tags_info):
                print(f"\n{GREEN}✨ All tags discovered!{END}")
                break

            # Show missing
            missing = [t for t in tags_info.keys() if t not in found_tags]
            ts = time.strftime("%H:%M:%S")
            print(f"  [{ts}] ⏳ Attempt {attempt}/{max_attempts}: Waiting for {missing}...")
            
            time.sleep(2)
                
        except Exception as e:
            print(f"Discovery poll error: {e}")
            break
            
    return mapping
