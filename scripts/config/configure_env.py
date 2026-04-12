import os
import platform
import secrets
import sys
from datetime import datetime

# ANSI colors for nice UI
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
END = "\033[0m"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_FILE = os.path.join(REPO_ROOT, ".env")
EXAMPLE_FILE = os.path.join(REPO_ROOT, ".env.example")

# Rex Guardrail: Required variables for system integrity
REQUIRED_VARS = [
    "REPO_ROOT",
    "MASTER_IP",
    "DASHBOARD_PORT",
    "HTTP_PORT",
    "DATA_DIR",
    "CONFIG_DIR",
    "DOMAIN",
    "BASE_DOMAIN",
    "VPN_USER",
    "VPN_PASSWORD",
    "DASHBOARD_SECRET",
    "CF_TUNNEL_TOKEN",
    "TELEGRAM_BOT_TOKEN"
]

def get_input(prompt, default=None):
    if default:
        user_input = input(f"{prompt} [{YELLOW}{default}{END}]: ").strip()
        return user_input if user_input else default
    return input(f"{prompt}: ").strip()

def load_current_env():
    env_vars = {}
    source_file = ENV_FILE if os.path.exists(ENV_FILE) else EXAMPLE_FILE
    
    if os.path.exists(source_file):
        with open(source_file, 'r', encoding='utf-8') as f:
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
    is_windows = platform.system().lower() == "windows"
    new_env["REPO_ROOT"] = current_env.get("REPO_ROOT", REPO_ROOT)
    
    # Platform-aware defaults for a smooth experience
    repo_media = os.path.join(REPO_ROOT, "media")
    default_data = "D:" if (is_windows and os.path.exists("D:\\")) else ("/mnt" if not is_windows else repo_media)
    default_config = "C:\\M3tal\\Config" if is_windows else "/docker/configs"

    current_data = current_env.get("DATA_DIR", default_data)
    current_config = current_env.get("CONFIG_DIR", default_config)
    
    # If the current value is a Linux placeholder and we are on Windows, swap it
    if is_windows:
        if current_data == "/mnt": current_data = default_data
        if current_config == "/docker/configs": current_config = default_config

    print(f"{BOLD}--- [1] System Settings ---{END}")
    new_env["MASTER_IP"] = get_input("Master Node IP", current_env.get("MASTER_IP", "127.0.0.1"))
    new_env["DASHBOARD_PORT"] = get_input("Dashboard UI Port", current_env.get("DASHBOARD_PORT", "8080"))
    new_env["HTTP_PORT"] = get_input("HTTP Gateway Port (80)", current_env.get("HTTP_PORT", "80"))
    
    # Robust DATA_DIR input with Windows validation
    while True:
        data_input = get_input("Global Data Directory", current_data)
        if is_windows and data_input.startswith("/") and not data_input.startswith("//"):
            print(f"{RED}[!] WARNING: You are on Windows but entered a Linux path ({data_input}).{END}")
            confirm_path = get_input("Are you sure? (y/n)", "n")
            if confirm_path.lower() == "y":
                new_env["DATA_DIR"] = data_input
                break
            continue
        new_env["DATA_DIR"] = data_input
        break

    new_env["CONFIG_DIR"] = get_input("Global Configuration Directory", current_config)
    new_env["DOMAIN"] = get_input("Public Domain (m3tal-media-server.xyz)", current_env.get("DOMAIN", "m3tal-media-server.xyz"))
    new_env["BASE_DOMAIN"] = get_input("Base Domain (same as public domain if unsure)", current_env.get("BASE_DOMAIN", new_env["DOMAIN"]))
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

    # 4. Notifications (Multi-Channel Audit Fix 5.7)
    print(f"{BOLD}--- [4] Telegram Multi-Channel Notifications ---{END}")
    new_env["TELEGRAM_BOT_TOKEN"] = get_input("Telegram Bot Token", current_env.get("TELEGRAM_BOT_TOKEN", current_env.get("TELEGRAM_TOKEN", "")))
    new_env["TG_CHAT_MODE"] = get_input("Telegram Chat Mode (1-4)", current_env.get("TG_CHAT_MODE", "1"))
    new_env["TG_MAIN_CHAT_ID"] = get_input("Main/Alert Chat ID", current_env.get("TG_MAIN_CHAT_ID", current_env.get("TELEGRAM_CHAT_ID", "")))
    new_env["TG_LOG_CHAT_ID"] = get_input("Logs Chat ID (0 to disable)", current_env.get("TG_LOG_CHAT_ID", "0"))
    new_env["TG_ERROR_CHAT_ID"] = get_input("Errors Chat ID (0 to disable)", current_env.get("TG_ERROR_CHAT_ID", "0"))
    new_env["TG_ALERT_CHAT_ID"] = get_input("Critical alerts Chat ID (0 to disable)", current_env.get("TG_ALERT_CHAT_ID", "0"))
    
    # Legacy fallbacks for backward compatibility
    new_env["TELEGRAM_TOKEN"] = new_env["TELEGRAM_BOT_TOKEN"]
    new_env["TELEGRAM_CHAT_ID"] = new_env["TG_MAIN_CHAT_ID"]
    print("")

    # 5. Cloudflare Tunnel
    print(f"{BOLD}--- [5] External Access (Cloudflare Tunnel) ---{END}")
    print(f"{YELLOW}⚠️  Crucial for remote access. Leave as 'replace_me' if using local only.{END}")
    new_env["CF_TUNNEL_TOKEN"] = get_input("Cloudflare Tunnel Token", current_env.get("CF_TUNNEL_TOKEN", "replace_me"))
    print("")

    # 6. Security (Auto-gen tokens if 'secret' or 'replace_me')
    print(f"{BOLD}--- [6] Security & Access ---{END}")
    if current_env.get("DASHBOARD_SECRET", "replace_me") == "replace_me":
        new_val = secrets.token_hex(32)
        print(f"Generated new Persistent Session Secret (DASHBOARD_SECRET)")
        new_env["DASHBOARD_SECRET"] = new_val
    print("")

    # Write to .env
    print(f"{BOLD}Writing configuration to .env...{END}")
    try:
        with open(ENV_FILE, 'w', encoding='utf-8') as f:
            f.write("# M3TAL Generated Environment File\n")
            f.write(f"# Updated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Sort keys into categories for readability
            categories = {
                "SYSTEM": ["REPO_ROOT", "PUID", "PGID", "TZ", "MASTER_IP", "DASHBOARD_PORT", "HTTP_PORT", "DOMAIN", "BASE_DOMAIN", "DATA_DIR", "CONFIG_DIR", "CF_TUNNEL_TOKEN"],
                "VPN": ["VPN_USER", "VPN_PASSWORD"],
                "AI": ["OLLAMA_URL", "AI_API_KEY"],
                "NOTIFY": ["TELEGRAM_BOT_TOKEN", "TG_CHAT_MODE", "TG_MAIN_CHAT_ID", "TG_LOG_CHAT_ID", "TG_ERROR_CHAT_ID", "TG_ALERT_CHAT_ID", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"],
                "DB": ["TATTOO_DB_PASSWORD"],
                "AUTH": ["DASHBOARD_SECRET"]
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
