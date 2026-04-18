import sys
from pathlib import Path

# Resolve repo root and inject paths
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))
sys.path.append(str(REPO_ROOT / "control-plane"))

try:
    from agents.telegram.discovery import discover_and_map
    from scripts.config.configure_env import GREEN, YELLOW, RED, BOLD, END, ENV_FILE
except ImportError as e:
    # Double fallback if running from root vs scripts dir
    try:
        from config.configure_env import GREEN, YELLOW, RED, BOLD, END, ENV_FILE
        from agents.telegram.discovery import discover_and_map
    except ImportError:
        print(f"Setup Error: {e}")
        sys.exit(1)

# Ensure BLUE is defined (L5 fix)
BLUE = "\033[94m"


def main():
    print(f"\n{BOLD}{BLUE}📡 M3TAL Telegram Auto-Discovery Wizard{END}")
    print("This tool will help you find your Chat IDs automatically.\n")
    
    if not BOT_TOKEN:
        print(f"{RED}[!] Error: TELEGRAM_BOT_TOKEN not found in .env{END}")
        return

    print(f"{BOLD}Step 1:{END} Open your Telegram app.")
    print(f"{BOLD}Step 2:{END} Send the following tags to your respective groups/channels:")
    print(f"  - {YELLOW}#m3tal_main{END}    (required)")
    print(f"  - {YELLOW}#m3tal_logs{END}")
    print(f"  - {YELLOW}#m3tal_error{END}")
    print(f"  - {YELLOW}#m3tal_alert{END}")
    print(f"  - {YELLOW}#m3tal_action{END}")
    print(f"  - {YELLOW}#m3tal_docker{END}\n")
    
    input(f"{GREEN}Press Enter when you have sent the tags...{END}")
    
    print(f"\n{BLUE}[*] Scanning for tags...{END}")
    mapping = discover_and_map()
    
    if not mapping:
        print(f"{RED}[!] No tags found. Make sure the bot is added to the groups and you sent the tags.{END}")
        return
        
# TODO: try again to find the chat id for the user who sent the tag 

    print(f"\n{GREEN}Found {len(mapping)} chat mappings:{END}")
    for key, cid in mapping.items():
        print(f"  ✅ {key} = {cid}")
        
    confirm = input(f"\n{BOLD}Apply these to your .env file? (y/n): {END}").strip().lower()
    
    if confirm == "y":
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        new_lines = []
        for line in lines:
            updated = False
            for key, cid in mapping.items():
                if line.startswith(f"{key}="):
                    new_lines.append(f"{key}={cid}\n")
                    updated = True
                    break
            if not updated:
                new_lines.append(line)
                
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
            
        print(f"\n{GREEN}{BOLD}✅ .env updated successfully!{END}")
    else:
        print(f"\n{YELLOW}Discarding changes.{END}")

if __name__ == "__main__":
    main()
