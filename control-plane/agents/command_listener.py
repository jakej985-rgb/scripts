import os
import sys
import json
import time
import subprocess
import secrets
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.telegram import is_allowed_user
from agents import telegram
from utils.paths import REGISTRY_JSON

START_TIME = datetime.now()

# =========================
# Helpers
# =========================

def get_allowed_containers():
    from config.telegram import ALLOWED_DOCKER_RESTARTS
    static_allowed = [s.strip() for s in ALLOWED_DOCKER_RESTARTS if s.strip()]

    if not REGISTRY_JSON.exists():
        return static_allowed

    try:
        with open(REGISTRY_JSON, "r") as f:
            registry = json.load(f)

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


# =========================
# Command Handlers
# =========================

def handle_ping(msg):
    telegram.send_direct(msg["chat"]["id"], "✅ <b>M3TAL Online</b>")

def handle_myid(msg):
    telegram.send_direct(msg["chat"]["id"], f"<code>{msg['from']['id']}</code>")

def handle_uptime(msg):
    delta = datetime.now() - START_TIME
    h, r = divmod(int(delta.total_seconds()), 3600)
    m, s = divmod(r, 60)
    telegram.send_direct(msg["chat"]["id"], f"{h}h {m}m {s}s")

def handle_help(msg):
    telegram.send_direct(msg["chat"]["id"],
        "/ping\n/status\n/status agents\n/docker status\n/docker restart <name>\n")

# =========================
# Command Core
# =========================

_cmd_cooldowns = {}
CMD_COOLDOWN = 3

def is_rate_limited(uid):
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
    if not uid or not is_allowed_user(uid):
        return

    # FIX: safer TTL check (no false drops)
    msg_date = msg.get("date")
    if msg_date and abs(time.time() - msg_date) > 600:
        print(f"[CMD] Dropped old msg ({uid})")
        return

    if is_rate_limited(uid):
        telegram.send_direct(msg["chat"]["id"], "⏳ Slow down")
        return

    text = msg["text"].strip()
    if not text.startswith("/"):
        return

    parts = text.split()
    cmd = parts[0].split("@")[0].lower()
    args = parts[1:]

    print(f"[CMD] {cmd} from {uid}")

    if cmd == "/ping":
        handle_ping(msg)

    elif cmd == "/help":
        handle_help(msg)

    elif cmd == "/myid":
        handle_myid(msg)

    elif cmd == "/uptime":
        handle_uptime(msg)

    elif cmd == "/status":
        from utils.paths import HEALTH_JSON

        status_msg = "🏥 <b>Status</b>\n"
        if HEALTH_JSON.exists():
            try:
                data = json.loads(HEALTH_JSON.read_text())
                status_msg += f"{data.get('status','unknown')}"
            except:
                status_msg += "corrupt"
        else:
            status_msg += "missing"

        telegram.send_direct(msg["chat"]["id"], status_msg)

    elif cmd == "/docker":
        if not args:
            telegram.send_direct(msg["chat"]["id"], "usage")
            return

        if args[0] == "status":
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}} {{.Status}}"],
                capture_output=True, text=True
            )
            telegram.send_direct(msg["chat"]["id"], f"<pre>{result.stdout}</pre>")


# =========================
# 🔥 FIXED LISTENER LOOP
# =========================

def listen_commands():
    telegram.start()

    from utils.paths import TELEGRAM_OFFSET_TXT

    offset = 0
    if TELEGRAM_OFFSET_TXT.exists():
        try:
            offset = int(TELEGRAM_OFFSET_TXT.read_text().strip())
        except:
            offset = 0

    print(f"[CMD] Listener running (offset={offset})")

    while True:
        try:
            updates = telegram.router.get_new_updates(
                offset=offset,
                timeout=30   # 🔥 CRITICAL FIX (long polling)
            )

            if not updates:
                continue

            for update in updates:
                print(f"[CMD] Update received")

                try:
                    handle_command(update)
                except Exception as e:
                    print(f"[CMD ERROR] {e}")

                offset = update["update_id"] + 1

            TELEGRAM_OFFSET_TXT.write_text(str(offset))

        except Exception as e:
            print(f"[CMD LOOP ERROR] {e}")
            time.sleep(2)


# =========================
# Entry
# =========================

if __name__ == "__main__":
    from utils.guards import wrap_agent

    print("[TELEGRAM] Listener starting...")

    # IMPORTANT: no interval loop here anymore
    wrap_agent("command_listener", listen_commands)
