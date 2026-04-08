#!/usr/bin/env python3
import os
import secrets
import sys

# ANSI colors for nice UI
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
END = "\033[0m"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(REPO_ROOT, ".env")
EXAMPLE_FILE = os.path.join(REPO_ROOT, ".env.example")

def get_input(prompt, default=None):
    if default:
        user_input = input(f"{prompt} [{YELLOW}{default}{END}]: ").strip()
        return user_input if user_input else default
    return input(f"{prompt}: ").strip()

def load_current_env():
    env_vars = {}
    source_file = ENV_FILE if os.path.exists(ENV_FILE) else EXAMPLE_FILE
    
    if os.path.exists(source_file):
        with open(source_file, 'r') as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, val = line.strip().split("=", 1)
                    env_vars[key] = val
    return env_vars

def main():
    print(f"\n{BOLD}{BLUE}🚀 M3TAL configuration Wizard{END}")
    print(f"This script will help you set up your {BOLD}.env{END} file safely.\n")

    current_env = load_current_env()
    new_env = current_env.copy()

    # 1. System Config
    print(f"{BOLD}--- [1] System Settings ---{END}")
    new_env["MASTER_IP"] = get_input("Master Node IP", current_env.get("MASTER_IP", "127.0.0.1"))
    new_env["DASHBOARD_PORT"] = get_input("Dashboard UI Port", current_env.get("DASHBOARD_PORT", "8080"))
    new_env["HTTP_PORT"] = get_input("HTTP Gateway Port (80)", current_env.get("HTTP_PORT", "80"))
    new_env["DATA_DIR"] = get_input("Global Data Directory", current_env.get("DATA_DIR", "/mnt"))
    new_env["DOMAIN"] = get_input("Local Domain (for Traefik)", current_env.get("DOMAIN", "local"))
    print("")

    # 2. VPN Setup
    print(f"{BOLD}--- [2] VPN Credentials (required for Gluetun) ---{END}")
    new_env["VPN_USER"] = get_input("VPN Username", current_env.get("VPN_USER"))
    new_env["VPN_PASSWORD"] = get_input("VPN Password", current_env.get("VPN_PASSWORD"))
    print("")

    # 3. AI & LLM
    print(f"{BOLD}--- [3] AI & Intelligence ---{END}")
    new_env["OLLAMA_URL"] = get_input("Ollama Endpoint URL", current_env.get("OLLAMA_URL", "http://localhost:11434"))
    new_env["AI_API_KEY"] = get_input("OpenAI/Anthropic API Key (Optional)", current_env.get("AI_API_KEY", ""))
    print("")

    # 4. Notifications
    print(f"{BOLD}--- [4] Notifications ---{END}")
    new_env["TELEGRAM_TOKEN"] = get_input("Telegram Bot Token", current_env.get("TELEGRAM_TOKEN", ""))
    new_env["TELEGRAM_CHAT_ID"] = get_input("Telegram Chat ID", current_env.get("TELEGRAM_CHAT_ID", ""))
    print("")

    # 5. Security (Auto-gen tokens if 'secret' or 'replace_me')
    print(f"{BOLD}--- [5] Security & Access ---{END}")
    if current_env.get("DASHBOARD_SECRET", "replace_me") == "replace_me":
        new_val = secrets.token_hex(32)
        print(f"Generated new Persistent Session Secret (DASHBOARD_SECRET)")
        new_env["DASHBOARD_SECRET"] = new_val

    for token_key in ["ADMIN_TOKEN", "OPS_TOKEN", "VIEW_TOKEN"]:
        current_val = current_env.get(token_key, "")
        if current_val in ["secret", "replace_me", ""]:
            new_val = secrets.token_urlsafe(32)
            print(f"Generated new {token_key}: {GREEN}{new_val}{END}")
            new_env[token_key] = new_val
    print("")

    # Write to .env
    print(f"{BOLD}Writing configuration to .env...{END}")
    try:
        with open(ENV_FILE, 'w') as f:
            f.write("# M3TAL Generated Environment File\n")
            f.write(f"# Updated at: {os.popen('date').read().strip()}\n\n")
            
            # Sort keys into categories for readability
            categories = {
                "SYSTEM": ["PUID", "PGID", "TZ", "MASTER_IP", "DASHBOARD_PORT", "HTTP_PORT", "DOMAIN", "DATA_DIR"],
                "VPN": ["VPN_USER", "VPN_PASSWORD"],
                "AI": ["OLLAMA_URL", "AI_API_KEY"],
                "NOTIFY": ["TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"],
                "DB": ["TATTOO_DB_PASSWORD"],
                "AUTH": ["DASHBOARD_SECRET", "ADMIN_TOKEN", "OPS_TOKEN", "VIEW_TOKEN"]
            }

            for cat, keys in categories.items():
                f.write(f"# --- {cat} ---\n")
                for k in keys:
                    val = new_env.get(k, current_env.get(k, ""))
                    f.write(f"{k}={val}\n")
                f.write("\n")
                
        print(f"\n{GREEN}{BOLD}✅ Configuration complete!{END}")
        print(f"You can now run {BOLD}bash control-plane/run.sh{END} to start the server.\n")
    except Exception as e:
        print(f"{RED}Error writing .env: {e}{END}")

if __name__ == "__main__":
    main()
