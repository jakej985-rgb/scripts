import time
import subprocess
import json
import os
from datetime import datetime
from control_plane.config.telegram import is_allowed_user, BOT_TOKEN
from control_plane.agents.utils.telegram import router, logger
from control_plane.agents.utils.paths import REGISTRY_JSON, STATE_DIR

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
            # registry.json structure: {"containers": {"name": {...}}}
            return list(registry.get("containers", {}).keys())
    except Exception as e:
        print(f"[CMD] Error reading registry: {e}")
        return []

def handle_ping(msg):
    router.send(msg["chat"]["id"], "✅ <b>M3TAL Online</b>\nStatus: Healthy\nQueue: Active")

def handle_myid(msg):
    uid = msg["from"]["id"]
    router.send(msg["chat"]["id"], f"Your Telegram ID: <code>{uid}</code>")

def handle_uptime(msg):
    delta = datetime.now() - START_TIME
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"
    router.send(msg["chat"]["id"], f"🕒 <b>System Uptime:</b> {uptime_str}")

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
    )
    router.send(msg["chat"]["id"], help_text)

def handle_docker(msg, args):
    if not args:
        router.send(msg["chat"]["id"], "Usage: /docker [status|logs|restart] [container_name]")
        return

    cmd = args[0].lower()
    allowed = get_allowed_containers()

    if cmd == "status":
        try:
            result = subprocess.run(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Image}}"], capture_output=True, text=True, timeout=10)
            router.send(msg["chat"]["id"], f"🐳 <b>Docker Status:</b>\n<pre>{result.stdout}</pre>")
        except Exception as e:
            router.send(msg["chat"]["id"], f"❌ Error: {e}")

    elif cmd == "logs":
        if len(args) < 2:
            router.send(msg["chat"]["id"], "Usage: /docker logs [container_name]")
            return
        name = args[1]
        if name not in allowed:
            router.send(msg["chat"]["id"], f"🚫 Container <code>{name}</code> is not in registry whitelist.")
            return
        try:
            result = subprocess.run(["docker", "logs", "--tail", "20", name], capture_output=True, text=True, timeout=10)
            # Combine stdout and stderr since logs often go to both
            log_out = (result.stdout + result.stderr).strip()
            router.send(msg["chat"]["id"], f"📄 <b>Logs for {name}:</b>\n<pre>{log_out}</pre>")
        except Exception as e:
            router.send(msg["chat"]["id"], f"❌ Error: {e}")

    elif cmd == "restart":
        if len(args) < 2:
            router.send(msg["chat"]["id"], "Usage: /docker restart [container_name]")
            return
        name = args[1]
        if name not in allowed:
            router.send(msg["chat"]["id"], f"🚫 Container <code>{name}</code> is not in registry whitelist.")
            return
        try:
            router.send(msg["chat"]["id"], f"⏳ Restarting <code>{name}</code>...")
            subprocess.run(["docker", "restart", name], timeout=30)
            router.send(msg["chat"]["id"], f"✅ Container <code>{name}</code> restarted.")
            logger.action(f"User {msg['from']['id']} restarted {name} via Telegram")
        except Exception as e:
            router.send(msg["chat"]["id"], f"❌ Error restarting {name}: {e}")

def handle_command(update):
    msg = update.get("message")
    if not msg or "text" not in msg:
        return

    uid = msg["from"]["id"]
    if not is_allowed_user(uid):
        # Silent fail for unauthorized
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
    elif cmd == "/status":
        from control_plane.agents.utils.paths import HEALTH_JSON
        status_msg = "🏥 <b>M3TAL System Health:</b>\n"
        if HEALTH_JSON.exists():
            try:
                data = json.loads(HEALTH_JSON.read_text())
                status = data.get("status", "unknown").upper()
                mode = data.get("mode", "unknown")
                ts = datetime.fromtimestamp(data.get("timestamp", 0)).strftime("%H:%M:%S")
                status_msg += f"Status: {status}\nMode: {mode}\nLast update: {ts}\n"
            except:
                status_msg += "Status: [CORRUPT]\n"
        else:
            status_msg += "Status: [FILE MISSING]\n"
        
        if len(args) > 0 and args[0].lower() == "agents":
            from control_plane.agents.utils.paths import RESTARTS_JSON
            status_msg += "\n🤖 <b>Agent Stability:</b>\n"
            if RESTARTS_JSON.exists():
                try:
                    restarts = json.loads(RESTARTS_JSON.read_text())
                    for name, meta in restarts.items():
                        count = meta.get("count", 0)
                        icon = "✅" if count == 0 else "⚠️" if count < 5 else "❌"
                        status_msg += f"{icon} {name}: {count} fails\n"
                except:
                    status_msg += "Error reading agent state."
            else:
                status_msg += "No failure history."
        
        router.send(msg["chat"]["id"], status_msg)

def run():
    print("[TELEGRAM] Starting Listener Agent...")
    
    # Ignore history on startup if offset not set
    if router.load_offset() == 0:
        print("[TELEGRAM] No offset found, initializing to latest...")
        router.initialize_offset()

    while True:
        try:
            for update in router.get_updates():
                handle_command(update)
            time.sleep(2)
        except Exception as e:
            print(f"[TELEGRAM LOOP ERR] {e}")
            time.sleep(5)

if __name__ == "__main__":
    run()
