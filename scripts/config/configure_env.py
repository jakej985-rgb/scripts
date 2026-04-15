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

# Inject M3TAL Control Plane paths for discovery tools
CONTROL_PLANE = os.path.join(REPO_ROOT, "control-plane")
if CONTROL_PLANE not in sys.path:
    sys.path.append(CONTROL_PLANE)
    sys.path.append(os.path.join(CONTROL_PLANE, "agents"))

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
    "TELEGRAM_BOT_TOKEN",
    "TG_CHAT_COUNT",
    "DOCKER_API_VERSION"
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
    
    # Docker API Discovery
    default_api = current_env.get("DOCKER_API_VERSION", "1.41")
    try:
        import subprocess
        auto_api = subprocess.check_output(["docker", "version", "--format", "{{.Client.APIVersion}}"], text=True, stderr=subprocess.DEVNULL).strip()
        if auto_api:
            default_api = auto_api
    except:
        pass
        
    new_env["DOCKER_API_VERSION"] = get_input("Docker API Version", default_api)
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

    # 4. Notifications (Multi-Channel v2 - Smart Discovery)
    print(f"{BOLD}--- [4] Telegram Multi-Channel Notifications ---{END}")
    
    bot_token = get_input("Telegram Bot Token", current_env.get("TELEGRAM_BOT_TOKEN", current_env.get("TELEGRAM_TOKEN", "")))
    new_env["TELEGRAM_BOT_TOKEN"] = bot_token
    
    chat_count = int(get_input("Telegram Chat Count (1-6)", current_env.get("TG_CHAT_COUNT", "1")))
    new_env["TG_CHAT_COUNT"] = str(chat_count)
    
    cur_auto = current_env.get("TG_AUTO_DISCOVER", "false").lower()
    def_auto = "y" if cur_auto in ("true", "y") else "n"
    auto_discover = get_input("Enable Auto-Discovery (y/n)", def_auto).lower()
    new_env["TG_AUTO_DISCOVER"] = "true" if auto_discover == "y" else "false"
    
    allowed_users = get_input("Allowed User IDs (comma-separated)", current_env.get("ALLOWED_USERS", "0"))
    new_env["ALLOWED_USERS"] = allowed_users

    mapping = {}
    if auto_discover == "y":
        try:
            # Set bot token in environment temporarily so discovery can use it
            os.environ["TELEGRAM_BOT_TOKEN"] = bot_token
            from agents.telegram.discovery import discover_and_map
            mapping = discover_and_map()
            
            if mapping:
                print(f"\n{GREEN}--- Discovered Chats ---{END}")
                for k, v in mapping.items():
                    print(f"  ✅ {k} = {v}")
            else:
                print(f"\n{YELLOW}⚠ No tags discovered. Falling back to manual input.{END}")
        except Exception as e:
            print(f"\n{RED}[!] Auto-discovery error: {e}{END}")

    # Helper to ask only if not in mapping
    def get_chat_id(key, label):
        val = mapping.get(key)
        if val:
            return str(val)
        return get_input(label, current_env.get(key, "0"))

    if chat_count >= 1:
        new_env["TG_MAIN_CHAT_ID"] = get_chat_id("TG_MAIN_CHAT_ID", "Main Chat ID")
    
    if chat_count >= 2:
        new_env["TG_ERROR_CHAT_ID"] = get_chat_id("TG_ERROR_CHAT_ID", "Errors Chat ID")
        
    if chat_count >= 3:
        new_env["TG_LOG_CHAT_ID"] = get_chat_id("TG_LOG_CHAT_ID", "Logs Chat ID")
        
    if chat_count >= 4:
        new_env["TG_ALERT_CHAT_ID"] = get_chat_id("TG_ALERT_CHAT_ID", "Critical Alerts Chat ID")
        
    if chat_count >= 5:
        new_env["TG_ACTION_CHAT_ID"] = get_chat_id("TG_ACTION_CHAT_ID", "Action/Command Chat ID")
        
    if chat_count == 6:
        new_env["TG_DOCKER_CHAT_ID"] = get_chat_id("TG_DOCKER_CHAT_ID", "Docker Telemetry Chat ID")

    # Legacy fallbacks for backward compatibility
    new_env["TELEGRAM_TOKEN"] = new_env["TELEGRAM_BOT_TOKEN"]
    new_env["TELEGRAM_CHAT_ID"] = new_env.get("TG_MAIN_CHAT_ID", "0")
    print("")

    # 5. Cloudflare Tunnel
    print(f"{BOLD}--- [5] External Access (Cloudflare Tunnel) ---{END}")
    print(f"{YELLOW}⚠️  Crucial for remote access. Leave as 'replace_me' if using local only.{END}")
    new_env["CF_TUNNEL_TOKEN"] = get_input("Cloudflare Tunnel Token", current_env.get("CF_TUNNEL_TOKEN", "replace_me"))
    print("")

    # 6. Security & Final Review
    print(f"{BOLD}--- [6] Security & Access ---{END}")
    if current_env.get("DASHBOARD_SECRET", "replace_me") == "replace_me":
        new_val = secrets.token_hex(32)
        print(f"Generated new Persistent Session Secret (DASHBOARD_SECRET)")
        new_env["DASHBOARD_SECRET"] = new_val
    print("")

    # FINAL REVIEW
    print(f"{BOLD}--- Final Configuration Review ---{END}")
    for k, v in new_env.items():
        if "PASSWORD" in k or "TOKEN" in k or "SECRET" in k or "KEY" in k:
            # Mask secrets
            masked = v[:5] + "..." if len(str(v)) > 5 else "***"
            print(f"  {k}: {masked}")
        else:
            print(f"  {k}: {v}")
    
    confirm = input(f"\n{YELLOW}Accept this configuration and write to .env? (y/n): {END}").strip().lower()
    if confirm != "y":
        print(f"\n{RED}Aborted. No changes made.{END}")
        return

    # Write to .env
    print(f"{BOLD}Writing configuration to .env...{END}")
    try:
        with open(ENV_FILE, 'w', encoding='utf-8') as f:
            f.write("# M3TAL Generated Environment File\n")
            f.write(f"# Updated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Sort keys into categories for readability
            categories = {
                "SYSTEM": ["REPO_ROOT", "DOCKER_API_VERSION", "PUID", "PGID", "TZ", "MASTER_IP", "DASHBOARD_PORT", "HTTP_PORT", "DOMAIN", "BASE_DOMAIN", "DATA_DIR", "CONFIG_DIR", "CF_TUNNEL_TOKEN"],
                "VPN": ["VPN_USER", "VPN_PASSWORD"],
                "AI": ["OLLAMA_URL", "AI_API_KEY"],
                "NOTIFY": ["TELEGRAM_BOT_TOKEN", "TG_CHAT_COUNT", "TG_AUTO_DISCOVER", "ALLOWED_USERS", "TG_MAIN_CHAT_ID", "TG_LOG_CHAT_ID", "TG_ERROR_CHAT_ID", "TG_ALERT_CHAT_ID", "TG_ACTION_CHAT_ID", "TG_DOCKER_CHAT_ID", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"],
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
        print(f"You can now run {BOLD}python m3tal.py run{END} to start the server.\n")
    except Exception as e:
        print(f"{RED}Error writing .env: {e}{END}")

if __name__ == "__main__":
    main()
