import sys
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

# M3TAL Telegram Command Listener (v3.5 Bulletproof)
# Responsibility: Interactive control, log inspection, and system status.

# Bootstrap path system
_BOOT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(_BOOT_ROOT / "control-plane"))

from agents import telegram
from config.telegram import is_allowed_user
from utils.paths import REGISTRY_JSON, HEALTH_JSON, TELEGRAM_OFFSET_TXT
from utils.guards import wrap_agent, SHUTDOWN_EVENT

START_TIME = datetime.now()

# --- Helpers ------------------------------------------------------------------

def get_allowed_containers():
    """Returns a list of containers allowed for interactive control."""
    from config.telegram import ALLOWED_DOCKER_RESTARTS
    static_allowed = [s.strip() for s in ALLOWED_DOCKER_RESTARTS if s.strip()]

    if not REGISTRY_JSON.exists():
        return static_allowed

    try:
        with open(REGISTRY_JSON, "r") as f:
            registry = json.load(f)
        
        # Merge static list with dynamic registry
        containers = registry.get("containers", [])
        if isinstance(containers, dict):
            dynamic_allowed = list(containers.keys())
        elif isinstance(containers, list):
            dynamic_allowed = containers
        else:
            dynamic_allowed = []

        return list(set(static_allowed + dynamic_allowed))
    except Exception as e:
        print(f"[CMD] Registry error: {e}")
        return static_allowed

# --- Command Handlers ---------------------------------------------------------

def handle_status(msg, args):
    """Provides high-level system or agent status."""
    if args and args[0] == "agents":
        # Detailed agent health from health.json
        if HEALTH_JSON.exists():
            try:
                data = json.loads(HEALTH_JSON.read_text())
                agents = data.get("agents", {})
                status_lines = [f"<b>Agent Health</b> (Score: {data.get('score', 0)}%)"]
                for name, stats in agents.items():
                    emoji = "✅" if stats.get("status") == "healthy" else "❌"
                    status_lines.append(f"{emoji} {name}")
                telegram.send_direct(msg["chat"]["id"], "\n".join(status_lines))
            except:
                telegram.send_direct(msg["chat"]["id"], "❌ Error reading health state.")
        else:
            telegram.send_direct(msg["chat"]["id"], "⚠️ health.json not found.")
    else:
        # Generic system status
        uptime = str(datetime.now() - START_TIME).split(".")[0]
        telegram.send_direct(msg["chat"]["id"], f"🏥 <b>M3TAL System</b>\nUptime: <code>{uptime}</code>\nStatus: <b>HEALTHY</b>")

def handle_docker(msg, args):
    """Container management: status, restart."""
    if not args:
        telegram.send_direct(msg["chat"]["id"], "Usage: <code>/docker [status|restart]</code>")
        return

    cmd = args[0].lower()
    if cmd == "status":
        try:
            res = subprocess.run(["docker", "ps", "--format", "{{.Names}} | {{.Status}}"], capture_output=True, text=True)
            output = res.stdout if res.stdout else "No containers running."
            telegram.send_direct(msg["chat"]["id"], f"🐳 <b>Docker Status</b>\n<pre>{output}</pre>")
        except Exception as e:
            telegram.send_direct(msg["chat"]["id"], f"❌ Docker error: {e}")

    elif cmd == "restart":
        if len(args) < 2:
            telegram.send_direct(msg["chat"]["id"], "Usage: <code>/docker restart <name></code>")
            return
        
        target = args[1]
        allowed = get_allowed_containers()
        
        if target not in allowed:
            telegram.send_direct(msg["chat"]["id"], f"🚫 <b>Access Denied</b>: '{target}' is not in the allowed list.")
            return

        telegram.send_direct(msg["chat"]["id"], f"⏳ Restarting <code>{target}</code>...")
        try:
            subprocess.run(["docker", "restart", target], check=True)
            telegram.send_direct(msg["chat"]["id"], f"✅ Container <code>{target}</code> restarted successfully.")
        except Exception as e:
            telegram.send_direct(msg["chat"]["id"], f"❌ Failed to restart <code>{target}</code>: {e}")

def handle_logs(msg, args):
    """Fetches recent logs for a service."""
    if not args:
        telegram.send_direct(msg["chat"]["id"], "Usage: <code>/logs <service_name></code>")
        return
    
    target = args[0]
    allowed = get_allowed_containers()
    if target not in allowed:
         telegram.send_direct(msg["chat"]["id"], "🚫 Unauthorized or unknown service.")
         return

    try:
        # Fetch last 30 lines
        res = subprocess.run(["docker", "logs", "--tail", "30", target], capture_output=True, text=True)
        logs = res.stdout if res.stdout else res.stderr
        if not logs: logs = "(no output)"
        telegram.send_direct(msg["chat"]["id"], f"📄 <b>Logs: {target}</b>\n<pre>{logs[-3500:]}</pre>")
    except Exception as e:
        telegram.send_direct(msg["chat"]["id"], f"❌ Error: {e}")

# --- Core Loop ----------------------------------------------------------------

def process_update(update):
    msg = update.get("message")
    if not msg or "text" not in msg:
        return

    uid_raw = msg.get("from", {}).get("id")
    uid = None
    if uid_raw is not None:
        try:
            uid = int(uid_raw)
        except (TypeError, ValueError):
            uid = None
    if not uid or not is_allowed_user(uid):
        # We don't respond to unauthorized users to avoid being a spam vector
        return

    # TTL Check (v3.6): Ignore messages older than 10 minutes
    # We only reject strictly OLD messages (now - msg_date > 600)
    # We ALLOW future timestamps (msg_date > now) because of common Docker clock drift
    now = time.time()
    msg_date = msg.get("date", 0)
    
    if msg_date > now + 60:
        # Detect drift but allow the message
        print(f"⚠️ [CMD] Clock Drift Detected: Message timestamp {msg_date} is in the future relative to {int(now)}")
    
    if (now - msg_date) > 600:
        print(f"[CMD] Dropping expired message from {uid} (age: {int(now - msg_date)}s)")
        return

    text = msg.get("text", "").strip()
    if not text.startswith("/"):
        return

    parts = text.split()
    cmd = parts[0].split("@")[0].lower()
    args = parts[1:]

    print(f"[CMD] {cmd} from {uid}")

    if cmd == "/ping":
        telegram.send_direct(msg["chat"]["id"], "pong 🏓")
    elif cmd == "/status":
        handle_status(msg, args)
    elif cmd == "/docker":
        handle_docker(msg, args)
    elif cmd == "/logs":
        handle_logs(msg, args)
    elif cmd == "/myid":
        telegram.send_direct(msg["chat"]["id"], f"Your ID: <code>{uid}</code>")
    elif cmd == "/help":
        help_text = (
            "🤖 <b>M3TAL Bot Commands</b>\n\n"
            "/status - System health overview\n"
            "/status agents - Detailed agent health\n"
            "/docker status - List running containers\n"
            "/docker restart &lt;name&gt; - Restart a service\n"
            "/logs &lt;name&gt; - View recent logs\n"
            "/uptime - System start time\n"
            "/ping - Basic connectivity test"
        )
        telegram.send_direct(msg["chat"]["id"], help_text)
    elif cmd == "/uptime":
        uptime = str(datetime.now() - START_TIME).split(".")[0]
        telegram.send_direct(msg["chat"]["id"], f"Uptime: <code>{uptime}</code>")

def listen_loop(initial_offset):
    offset = initial_offset
    
    pulse_count = 0
    while not SHUTDOWN_EVENT.is_set():
        try:
            updates = telegram.router.get_new_updates(offset=offset, timeout=20)

            if updates:
                print(f"[CMD] Received {len(updates)} updates")
                for update in updates:
                    process_update(update)
                    offset = update["update_id"] + 1
                
                # Persistence
                TELEGRAM_OFFSET_TXT.write_text(str(offset))
            else:
                pulse_count += 1
                if pulse_count >= 50: # Log a pulse every ~15-20 minutes
                    print(f"[CMD] Pulse: Listener is alive (offset={offset})")
                    pulse_count = 0
            
        except Exception as e:
            print(f"❌ [CMD] Loop Error: {e}")
            time.sleep(5)
            
        time.sleep(1)

def main():
    # Subprocesses must start their own Telegram worker
    telegram.start()

    # Long polling cannot receive updates while a webhook is registered on the same bot.
    from agents.telegram import client as tg_client

    wh = tg_client.call_api("getWebhookInfo", timeout=15)
    if wh.get("ok"):
        wh_url = (wh.get("result") or {}).get("url") or ""
        if wh_url:
            print(
                f"[CMD] Webhook active ({wh_url!r}) — deleting so getUpdates polling works.",
                flush=True,
            )
            dropped = tg_client.call_api(
                "deleteWebhook",
                {"drop_pending_updates": False},
                timeout=15,
            )
            if not dropped.get("ok"):
                print(
                    f"[CMD] ⚠️ deleteWebhook failed: {dropped.get('description')}",
                    flush=True,
                )

    # 1. Load Offset
    offset = 0
    if TELEGRAM_OFFSET_TXT.exists():
        try:
            offset = int(TELEGRAM_OFFSET_TXT.read_text().strip())
        except:
            offset = 0
            
    # 2. Initial Sync (Drain pending backlog)
    # Telegram getUpdates requires monotonic offset; there is no "offset=-1" API.
    # Short-poll with timeout=0 until empty, then persist next offset.
    if offset == 0:
        try:
            print("[CMD] No offset file — draining pending updates to skip backlog...", flush=True)
            next_o = 0
            drained = 0
            for _ in range(500):
                batch = telegram.router.get_new_updates(offset=next_o, timeout=0)
                if not batch:
                    offset = next_o
                    break
                drained += len(batch)
                next_o = batch[-1]["update_id"] + 1
            else:
                offset = next_o
            TELEGRAM_OFFSET_TXT.write_text(str(offset))
            print(
                f"✅ [CMD] Synced offset={offset} (drained {drained} pending update(s)).",
                flush=True,
            )
        except Exception as e:
            print(f"⚠️ [CMD] Sync failed: {e}", flush=True)

    print(f"[CMD] Starting Listener (offset={offset})")
    listen_loop(offset)

if __name__ == "__main__":
    wrap_agent("command_listener", main)
