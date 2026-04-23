import os
import sys
import json
import time
import subprocess
import secrets
from datetime import datetime

# Standardize path for agent execution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.telegram import is_allowed_user
from agents import telegram
from utils.paths import REGISTRY_JSON

# M3TAL Command Listener Agent (Tier 2)
# Hardened remote control via Telegram with sandboxed Docker access

START_TIME = datetime.now()

def get_allowed_containers():
    """Fetches the whitelist of containers from registry.json."""
    if not REGISTRY_JSON.exists():
        return []
    try:
        with open(REGISTRY_JSON, "r") as f:
            registry = json.load(f)
        
        containers = registry.get("containers", [])
        if isinstance(containers, list):
            return containers
        elif isinstance(containers, dict):
            return list(containers.keys())
        return []
    except Exception as e:
        print(f"[CMD] Error reading registry: {e}")
        return []

def handle_ping(msg):
    telegram.send_direct(msg["chat"]["id"], "✅ <b>M3TAL Online</b>\nStatus: Healthy\nQueue: Active")

def handle_myid(msg):
    uid = msg["from"]["id"]
    telegram.send_direct(msg["chat"]["id"], f"Your Telegram ID: <code>{uid}</code>")

def handle_uptime(msg):
    delta = datetime.now() - START_TIME
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"
    telegram.send_direct(msg["chat"]["id"], f"🕒 <b>System Uptime:</b> {uptime_str}")

def handle_help(msg):
    help_text = (
        "🛠️ <b>M3TAL Control Plane Commands:</b>\n\n"
        "/ping - Check bot health\n"
        "/status - Overall system health\n"
        "/status agents - Check all agents\n"
        "/myid - Get your Telegram ID\n"
        "/uptime - System uptime\n"
        "/docker status - List containers\n"
        "/docker logs &lt;name&gt; - Get last 20 lines\n"
        "/docker restart &lt;name&gt; - Restart container\n"
        "/confirm &lt;id&gt; - Confirm a pending action\n"
    )
    telegram.send_direct(msg["chat"]["id"], help_text)

_pending_confirmations: dict[int, dict] = {} # {chat_id: {type: str, target: str, id: str, expires: float}}

def handle_confirm(msg, args):
    if not args:
        telegram.send_direct(msg["chat"]["id"], "Usage: /confirm [id]")
        return
    
    conf_id = args[0]
    chat_id = msg["chat"]["id"]
    pending = _pending_confirmations.get(chat_id)
    
    if not pending or pending["id"] != conf_id:
        telegram.send_direct(chat_id, "❌ Invalid or expired confirmation ID.")
        return
    
    if time.time() > pending["expires"]:
        telegram.send_direct(chat_id, "⏰ Confirmation ID has expired.")
        del _pending_confirmations[chat_id]
        return
    
    # Execute pending action
    if pending["type"] == "restart":
        name = pending["target"]
        try:
            # Audit Fix C2: Secondary validation against live docker ps
            live_ps = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=10)
            live_containers = [line.strip() for line in live_ps.stdout.split('\n') if line.strip()]
            
            if name not in live_containers:
                telegram.send_direct(chat_id, f"❌ Security/Logic Violation: Container <code>{name}</code> is no longer reachable or valid.")
                return

            telegram.send_direct(chat_id, f"⏳ <b>CONFIRMED:</b> Restarting <code>{name}</code>...")
            subprocess.run(["docker", "restart", name], timeout=30)
            telegram.send_direct(chat_id, f"✅ Container <code>{name}</code> restarted.")
            telegram.action(f"User {msg['from']['id']} RESTARTED {name} via Telegram (Confirmed)")
        except Exception as e:
            telegram.send_direct(chat_id, f"❌ Error restarting {name}: {e}")
        finally:
            if chat_id in _pending_confirmations:
                del _pending_confirmations[chat_id]

def handle_docker(msg, args):
    if not args:
        telegram.send_direct(msg["chat"]["id"], "Usage: /docker [status|logs|restart] [container_name]")
        return

    cmd = args[0].lower()
    allowed = get_allowed_containers()

    if cmd == "status":
        try:
            result = subprocess.run(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Image}}"], capture_output=True, text=True, timeout=10)
            telegram.send_direct(msg["chat"]["id"], f"🐳 <b>Docker Status:</b>\n<pre>{result.stdout}</pre>")
        except Exception as e:
            telegram.send_direct(msg["chat"]["id"], f"❌ Error: {e}")

    elif cmd == "logs":
        if len(args) < 2:
            telegram.send_direct(msg["chat"]["id"], "Usage: /docker logs [container_name]")
            return
        name = args[1]
        if name not in allowed:
            telegram.send_direct(msg["chat"]["id"], f"🚫 Container <code>{name}</code> is not in registry whitelist.")
            return
        try:
            result = subprocess.run(["docker", "logs", "--tail", "20", name], capture_output=True, text=True, timeout=10)
            # Combine stdout and stderr since logs often go to both
            log_out = (result.stdout + result.stderr).strip()
            telegram.send_direct(msg["chat"]["id"], f"📄 <b>Logs for {name}:</b>\n<pre>{log_out}</pre>")
        except Exception as e:
            telegram.send_direct(msg["chat"]["id"], f"❌ Error: {e}")

    elif cmd == "restart":
        if len(args) < 2:
            telegram.send_direct(msg["chat"]["id"], "Usage: /docker restart [container_name]")
            return
        name = args[1]
        if name not in allowed:
            telegram.send_direct(msg["chat"]["id"], f"🚫 Container <code>{name}</code> is not in registry whitelist.")
            return
        
        # Issue confirmation ID (Audit Fix 10)
        conf_id = secrets.token_hex(3).upper()
        _pending_confirmations[msg["chat"]["id"]] = {
            "type": "restart",
            "target": name,
            "id": conf_id,
            "expires": time.time() + 60
        }
        telegram.send_direct(msg["chat"]["id"], 
                            f"🛡️ <b>RESTART CONFIRMATION</b>\n"
                            f"Container: <code>{name}</code>\n"
                            f"Action expires in 60s.\n\n"
                            f"Send: <code>/confirm {conf_id}</code>")

_cmd_cooldowns: dict[int, float] = {}
CMD_COOLDOWN = 5  # seconds

def is_rate_limited(uid: int) -> bool:
    now = time.time()
    last = _cmd_cooldowns.get(uid, 0)
    if now - last < CMD_COOLDOWN:
        return True
    _cmd_cooldowns[uid] = now
    return False

def handle_command(update):
    msg = update.get("message")
    if not msg or "text" not in msg:
        return

    uid = msg.get("from", {}).get("id")
    if not uid:
        return

    if not is_allowed_user(uid):
        # Silent fail for unauthorized
        return

    if is_rate_limited(uid):
        telegram.send_direct(msg["chat"]["id"], "⏳ Rate limited. Wait a moment.")
        return

    text = msg["text"].strip()
    if not text.startswith("/"):
        return

    parts = text.split()
    cmd = parts[0].split("@")[0].lower() # Handle /cmd@BotName
    args = parts[1:]

    print(f"[CMD] Processing {cmd} from {uid}")

    if cmd == "/ping":
        handle_ping(msg)
    elif cmd == "/myid":
        handle_myid(msg)
    elif cmd == "/uptime":
        handle_uptime(msg)
    elif cmd == "/help" or cmd == "/start":
        handle_help(msg)
    elif cmd == "/docker":
        handle_docker(msg, args)
    elif cmd == "/confirm":
        handle_confirm(msg, args)
    elif cmd == "/status":
        from utils.paths import HEALTH_JSON
        status_msg = "🏥 <b>M3TAL System Health:</b>\n"
        if HEALTH_JSON.exists():
            try:
                data = json.loads(HEALTH_JSON.read_text())
                status = data.get("status", "unknown").upper()
                mode = data.get("mode", "unknown")
                ts = datetime.fromtimestamp(data.get("timestamp", 0)).strftime("%H:%M:%S")
                status_msg += f"Status: {status}\nMode: {mode}\nLast update: {ts}\n"
            except Exception:
                status_msg += "Status: [CORRUPT]\n"
        else:
            status_msg += "Status: [FILE MISSING]\n"
        
        if len(args) > 0 and args[0].lower() == "agents":
            from utils.paths import RESTARTS_JSON
            status_msg += "\n🤖 <b>Agent Stability:</b>\n"
            if RESTARTS_JSON.exists():
                try:
                    restarts = json.loads(RESTARTS_JSON.read_text())
                    for name, meta in restarts.items():
                        count = meta.get("count", 0)
                        icon = "✅" if count == 0 else "⚠️" if count < 5 else "❌"
                        status_msg += f"{icon} {name}: {count} fails\n"
                except Exception:
                    status_msg += "Error reading agent state."
            else:
                status_msg += "No failure history."
        
        telegram.send_direct(msg["chat"]["id"], status_msg)

def listen_commands():
    # Audit Fix 1.5: Start worker only when explicitly running loop
    if not telegram.is_available():
        telegram.start()
        
    from utils.paths import TELEGRAM_OFFSET_TXT
    offset = 0
    if TELEGRAM_OFFSET_TXT.exists():
        try:
            offset = int(TELEGRAM_OFFSET_TXT.read_text().strip())
        except Exception:
            pass

    try:
        updates = telegram.router.get_new_updates(offset=offset)
        if not updates:
            return
            
        for update in updates:
            try:
                handle_command(update)
            except Exception as e:
                print(f"[TELEGRAM CMD ERR] {e}")
            finally:
                offset = update["update_id"] + 1
                
        TELEGRAM_OFFSET_TXT.write_text(str(offset))
    except Exception as e:
        print(f"[TELEGRAM LOOP ERR] {e}")

if __name__ == "__main__":
    from utils.guards import wrap_agent
    from utils.paths import TELEGRAM_OFFSET_TXT
    
    print("[TELEGRAM] Initializing Listener Agent...")
    
    # Optional drain on first boot
    if not TELEGRAM_OFFSET_TXT.exists():
        offset = 0
        try:
            while True:
                updates = telegram.router.get_new_updates(offset=offset)
                if not updates:
                    break
                offset = updates[-1]["update_id"]
            TELEGRAM_OFFSET_TXT.write_text(str(offset))
            print(f"[TELEGRAM] Offset safely initialized to {offset}")
        except Exception as e:
            print(f"[TELEGRAM INIT ERR] {e}")
            
    wrap_agent("command_listener", listen_commands, interval=2)
