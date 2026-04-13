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
    Polls getUpdates and maps tags to Chat IDs.
    Supports both #m3tal_ prefix and simplified version.
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
    print("M3TAL is looking for tags like #main or #m3tal_main.")
    
    print(f"\n{BOLD}INSTRUCTIONS:{END}")
    print("1. Open your Telegram Bot.")
    print("2. Send tags (e.g., #logs or #m3tal_logs) to your chats.")
    input(f"3. {CYAN}Press Enter to start scanning...{END}")
    
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
            
            # --- Diagnostic for 401 ---
            if resp_raw.status_code == 401:
                print(f"  ❌ {RED}ERROR: 401 Unauthorized (Invalid Token).{END}")
                token_clean = (BOT_TOKEN or "").strip()
                print(f"     Token starts with: {token_clean[:12]}...")
                print(f"     Token length: {len(token_clean)}")
                if "\r" in (BOT_TOKEN or "") or "\n" in (BOT_TOKEN or ""):
                    print(f"     {YELLOW}WARNING: Hidden newlines detected in token string!{END}")
                return mapping

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
                if "#" in text:
                    print(f"    Saw: [ {text} ] in chat {chat_id}")

                # Detection Logic (Resistant to #m3tal_ prefix)
                tags_map = {
                    "main": "TG_MAIN_CHAT_ID",
                    "logs": "TG_LOG_CHAT_ID",
                    "log": "TG_LOG_CHAT_ID",
                    "error": "TG_ERROR_CHAT_ID",
                    "alert": "TG_ALERT_CHAT_ID",
                    "action": "TG_ACTION_CHAT_ID",
                    "docker": "TG_DOCKER_CHAT_ID"
                }
                
                for key, env_key in tags_map.items():
                    if f"#{key}" in text or f"#m3tal_{key}" in text:
                        if env_key not in mapping:
                            mapping[env_key] = chat_id
                            canonical_tag = f"#{key}"
                            if canonical_tag not in found_tags:
                                print(f"  ✅ {GREEN}Mapped {canonical_tag}{END} to {chat_id}")
                                found_tags.add(canonical_tag)
                                new_discovery = True
            
            if new_discovery:
                attempt = 0 

            # Normalize found_tags to match keys in tags_info for completion check
            unique_mapped = len({tags_map[t[1:]] for t in found_tags if t[1:] in tags_map})
            if unique_mapped >= 6:
                print(f"\n{GREEN}✨ All tags discovered!{END}")
                break

            ts = time.strftime("%H:%M:%S")
            print(f"  [{ts}] ⏳ Attempt {attempt}/{max_attempts}...")
            time.sleep(2)
                
        except Exception as e:
            print(f"Discovery poll error: {e}")
            break
            
    return mapping
