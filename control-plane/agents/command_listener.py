import sys
import os
import json
import time
import shutil
import platform
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

# M3TAL Telegram Command Listener (v4.0 — Full Command Suite)
# Responsibility: Interactive control, log inspection, and system status.

# Bootstrap path system
_BOOT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(_BOOT_ROOT / "control-plane"))

from agents import telegram
from agents.telegram import session
from config.telegram import is_allowed_user, ALLOWED_USERS
from utils.paths import (
    REGISTRY_JSON, HEALTH_JSON, TELEGRAM_OFFSET_TXT,
    HEALTH_REPORT_JSON, METRICS_JSON, STATE_DIR, REPO_ROOT, DOCKER_DIR,
)
from utils.guards import wrap_agent, SHUTDOWN_EVENT

# --- Mute State Path ---------------------------------------------------------
MUTE_STATE_JSON = STATE_DIR / "mute_state.json"

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


def get_all_containers(include_stopped=False):
    """Query Docker directly for ALL containers on the host.
    
    Returns a sorted list of container names. Used for the button picker
    so users can see everything that's running.
    """
    try:
        cmd = ["docker", "ps", "--format", "{{.Names}}"]
        if include_stopped:
            cmd.insert(2, "-a")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            return []
        names = [n.strip() for n in res.stdout.strip().splitlines() if n.strip()]
        return sorted(names)
    except Exception as e:
        print(f"[CMD] Docker query error: {e}")
        return []


def _fmt_container_list(prefix=""):
    """Returns a formatted HTML string listing all allowed containers."""
    allowed = get_allowed_containers()
    if not allowed:
        return f"{prefix}\n⚠️ No containers are currently configured."
    names = sorted(allowed)
    listing = "\n".join(f"  • <code>{n}</code>" for n in names)
    return f"{prefix}\n\n📦 <b>Available containers:</b>\n{listing}"

# --- Inline Keyboard Builders ------------------------------------------------

def _build_container_keyboard(prefix: str):
    """Build inline keyboard rows of container buttons (3 per row).
    
    Uses live Docker discovery — shows ALL running containers.
    """
    names = get_all_containers()
    if not names:
        return []
    rows = []
    for i in range(0, len(names), 3):
        row = [{"text": n, "callback_data": f"{prefix}:{n}"} for n in names[i:i+3]]
        rows.append(row)
    return rows


DOCKER_ACTIONS = {
    "status":  {"emoji": "📋", "label": "Status"},
    "restart": {"emoji": "🔄", "label": "Restart"},
    "stop":    {"emoji": "🛑", "label": "Stop"},
    "start":   {"emoji": "▶️", "label": "Start"},
    "inspect": {"emoji": "🔍", "label": "Inspect"},
    "logs":    {"emoji": "📄", "label": "Logs"},
}


def _build_docker_menu():
    """Build the top-level Docker action keyboard."""
    row = [
        {"text": f"{info['emoji']} {info['label']}", "callback_data": f"dkr:{action}"}
        for action, info in DOCKER_ACTIONS.items()
    ]
    rows = [row[i:i+3] for i in range(0, len(row), 3)]
    rows.append([{"text": "⬅️ Main Menu", "callback_data": "menu:main"}])
    return rows


# --- Full Button Menu System --------------------------------------------------

MENU_CATEGORIES = [
    {"text": "📊 Status",  "callback_data": "cat:status"},
    {"text": "🐳 Docker",  "callback_data": "cat:docker"},
    {"text": "🌐 Network", "callback_data": "cat:network"},
    {"text": "⚙️ System",  "callback_data": "cat:system"},
    {"text": "🤖 Bot",     "callback_data": "cat:bot"},
]


def _build_main_menu():
    """Build the top-level category menu."""
    rows = [[btn] for btn in MENU_CATEGORIES]
    return rows


def _build_category_menu(category: str):
    """Build a sub-menu for a specific category."""
    back = [{"text": "⬅️ Main Menu", "callback_data": "menu:main"}]

    if category == "status":
        return [
            [{"text": "📊 System Status",    "callback_data": "cmd:status"},
             {"text": "🩺 Agent Health",     "callback_data": "cmd:status_agents"}],
            [{"text": "📈 Resources",        "callback_data": "cmd:resources"},
             {"text": "💾 Disk Usage",       "callback_data": "cmd:disk"}],
            [{"text": "⏱ Uptime",           "callback_data": "cmd:uptime"},
             {"text": "🏓 Ping",             "callback_data": "cmd:ping"}],
            [{"text": "🆔 My ID",            "callback_data": "cmd:myid"}],
            back,
        ]

    if category == "docker":
        return _build_docker_menu()

    if category == "network":
        return [
            [{"text": "🌐 Public IP",        "callback_data": "cmd:ip"},
             {"text": "🔌 Ports",            "callback_data": "cmd:ports"}],
            [{"text": "🔀 Traefik Status",   "callback_data": "cmd:traefik"}],
            back,
        ]

    if category == "system":
        return [
            [{"text": "💾 Backup",           "callback_data": "cmd:backup"},
             {"text": "⚙️ Env Config",       "callback_data": "cmd:env"}],
            [{"text": "⬇️ Update Stacks",    "callback_data": "cmd:update"},
             {"text": "🔄 Reboot Host",      "callback_data": "cmd:reboot"}],
            back,
        ]

    if category == "bot":
        return [
            [{"text": "🔇 Mute Alerts",      "callback_data": "cmd:mute"},
             {"text": "🔔 Unmute",           "callback_data": "cmd:unmute"}],
            [{"text": "🔐 Allowed Users",    "callback_data": "cmd:who"}],
            back,
        ]

    return [back]


def send_main_menu(chat_id):
    """Send the main menu keyboard to a chat."""
    telegram.send_keyboard(
        chat_id,
        "🤖 <b>M3TAL Control Panel</b>\n\nSelect a category:",
        _build_main_menu(),
    )


# --- Callback Query Handler --------------------------------------------------

def _execute_command(chat, cmd_name, uid=None):
    """Execute a command by name from a button press.
    
    Uses a synthetic message dict to reuse existing handlers.
    """
    fake_msg = {"chat": {"id": chat}, "from": {"id": uid or 0}}

    if cmd_name == "status":
        handle_status(fake_msg, [])
    elif cmd_name == "status_agents":
        handle_status(fake_msg, ["agents"])
    elif cmd_name == "resources":
        handle_resources(fake_msg)
    elif cmd_name == "disk":
        handle_disk(fake_msg)
    elif cmd_name == "uptime":
        uptime = str(datetime.now() - START_TIME).split(".")[0]
        telegram.send_direct(chat, f"⏱ Uptime: <code>{uptime}</code>")
    elif cmd_name == "ping":
        telegram.send_direct(chat, "pong 🏓")
    elif cmd_name == "myid":
        telegram.send_direct(chat, f"🆔 Your ID: <code>{uid}</code>")
    elif cmd_name == "ip":
        handle_ip(fake_msg)
    elif cmd_name == "ports":
        handle_ports(fake_msg)
    elif cmd_name == "traefik":
        handle_traefik(fake_msg)
    elif cmd_name == "backup":
        handle_backup(fake_msg)
    elif cmd_name == "env":
        handle_env(fake_msg)
    elif cmd_name == "mute":
        handle_mute(fake_msg)
    elif cmd_name == "unmute":
        handle_mute(fake_msg, unmute=True)
    elif cmd_name == "who":
        handle_who(fake_msg)
    elif cmd_name == "reboot":
        # Dangerous — send confirmation button instead of executing
        telegram.send_keyboard(chat, (
            "⚠️ <b>REBOOT HOST</b>\n\n"
            "This will reboot the entire server.\n"
            "All containers will go down temporarily.\n\n"
            "Are you sure?"
        ), [
            [{"text": "✅ Yes, Reboot", "callback_data": "confirm:reboot"},
             {"text": "❌ Cancel",      "callback_data": "cancel:0"}],
        ])
    elif cmd_name == "update":
        # Dangerous — send confirmation button
        telegram.send_keyboard(chat, (
            "⚠️ <b>UPDATE ALL STACKS</b>\n\n"
            "This will pull latest images and recreate\n"
            "every compose stack.\n\n"
            "Are you sure?"
        ), [
            [{"text": "✅ Yes, Update", "callback_data": "confirm:update"},
             {"text": "❌ Cancel",      "callback_data": "cancel:0"}],
        ])
    else:
        telegram.send_direct(chat, f"❓ Unknown command: {cmd_name}")


def handle_callback(cbq):
    """Process an inline keyboard button press."""
    cbq_id = cbq.get("id", "")
    user = cbq.get("from", {})
    uid = user.get("id")
    chat = cbq.get("message", {}).get("chat", {}).get("id")
    data = cbq.get("data", "")

    if not uid or not chat or not data:
        return

    # Auth check
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return
    if not is_allowed_user(uid):
        telegram.answer_callback(cbq_id, "⛔ Not authorized.")
        return

    # Acknowledge button press immediately (removes spinner)
    telegram.answer_callback(cbq_id)

    parts = data.split(":", 1)
    if len(parts) != 2:
        return
    action_type, value = parts

    # --- Main Menu navigation ---
    if action_type == "menu":
        if value == "main":
            send_main_menu(chat)
        return

    # --- Category sub-menu ---
    if action_type == "cat":
        title_map = {
            "status":  "📊 <b>Status & Monitoring</b>",
            "docker":  "🐳 <b>Docker Management</b>",
            "network": "🌐 <b>Network & Routing</b>",
            "system":  "⚙️ <b>System & Maintenance</b>",
            "bot":     "🤖 <b>Bot Management</b>",
        }
        title = title_map.get(value, "📋 <b>Menu</b>")
        buttons = _build_category_menu(value)
        telegram.send_keyboard(chat, f"{title}\n\nSelect a command:", buttons)
        return

    # --- Direct command execution from button ---
    if action_type == "cmd":
        _execute_command(chat, value, uid)
        return

    # --- Confirmation for dangerous commands ---
    if action_type == "confirm":
        fake_msg = {"chat": {"id": chat}, "from": {"id": uid}}
        if value == "reboot":
            handle_reboot(fake_msg, ["confirm"])
        elif value == "update":
            handle_update(fake_msg, ["confirm"])
        return

    # --- Docker action menu button (e.g. "dkr:restart") ---
    if action_type == "dkr":
        if value == "status":
            try:
                res = subprocess.run(
                    ["docker", "ps", "--format", "{{.Names}} | {{.Status}}"],
                    capture_output=True, text=True, timeout=15,
                )
                output = res.stdout.strip() if res.stdout else "No containers running."
                telegram.send_direct(chat, f"🐳 <b>Docker Status</b>\n<pre>{output}</pre>")
            except Exception as e:
                telegram.send_direct(chat, f"❌ Docker error: {e}")
            return

        if value == "logs":
            # Show container picker for logs
            buttons = _build_container_keyboard("log")
            if not buttons:
                telegram.send_direct(chat, "⚠️ No containers available.")
                return
            buttons.append([{"text": "⬅️ Docker Menu", "callback_data": "cat:docker"}])
            telegram.send_keyboard(chat, "📄 <b>View Logs</b>\n\nSelect a service:", buttons)
            return

        # For restart/stop/start/inspect → show container picker
        info = DOCKER_ACTIONS.get(value, {})
        label = info.get("label", value)
        session.set(uid, {"flow": "docker", "action": value})
        buttons = _build_container_keyboard("ctr")
        if not buttons:
            telegram.send_direct(chat, "⚠️ No containers available.")
            session.clear(uid)
            return
        buttons.append([{"text": "⬅️ Docker Menu", "callback_data": "cat:docker"}])
        telegram.send_keyboard(
            chat,
            f"{info.get('emoji', '🐳')} Select container to <b>{label}</b>:",
            buttons,
        )
        return

    # --- Container selection button (e.g. "ctr:radarr") ---
    if action_type == "ctr":
        user_session = session.get(uid)
        if not user_session or user_session.get("flow") != "docker":
            telegram.send_direct(chat, "⚠️ Session expired. Send /docker to start over.")
            return

        docker_action = user_session.get("action")
        target = value
        session.clear(uid)

        if docker_action == "inspect":
            try:
                fmt = "{{.Config.Image}}|{{.State.Status}}|{{.State.StartedAt}}|{{.Created}}|{{.HostConfig.RestartPolicy.Name}}"
                res = subprocess.run(["docker", "inspect", "-f", fmt, target], capture_output=True, text=True, timeout=10)
                if res.returncode != 0:
                    telegram.send_direct(chat, f"❌ Container <code>{target}</code> not found.")
                    return
                p = res.stdout.strip().split("|")
                image, status, started, created, rpol = (p + [""]*5)[:5]
                pres = subprocess.run(
                    ["docker", "inspect", "-f",
                     "{{range $p, $c := .NetworkSettings.Ports}}{{$p}}->{{range $c}}{{.HostPort}}{{end}} {{end}}",
                     target],
                    capture_output=True, text=True, timeout=10,
                )
                ports = pres.stdout.strip() or "none"
                telegram.send_direct(chat, (
                    f"🔍 <b>Inspect: {target}</b>\n\n"
                    f"  <b>Image:</b> <code>{image}</code>\n"
                    f"  <b>Status:</b> {status}\n"
                    f"  <b>Started:</b> <code>{started[:19]}</code>\n"
                    f"  <b>Created:</b> <code>{created[:19]}</code>\n"
                    f"  <b>Restart:</b> {rpol}\n"
                    f"  <b>Ports:</b> <code>{ports}</code>"
                ))
            except Exception as e:
                telegram.send_direct(chat, f"❌ Inspect error: {e}")
            return

        # restart / stop / start
        verb = {"restart": "Restarting", "stop": "Stopping", "start": "Starting"}.get(docker_action, docker_action)
        emoji_ok = {"restart": "🔄", "stop": "🛑", "start": "▶️"}.get(docker_action, "✅")
        telegram.send_direct(chat, f"⏳ {verb} <code>{target}</code>...")
        try:
            subprocess.run(["docker", docker_action, target], check=True, timeout=60)
            telegram.send_direct(chat, f"{emoji_ok} Container <code>{target}</code> {docker_action}ed successfully.")
        except Exception as e:
            telegram.send_direct(chat, f"❌ Failed to {docker_action} <code>{target}</code>: {e}")
        return

    # --- Log container selection (e.g. "log:radarr") ---
    if action_type == "log":
        target = value
        session.clear(uid)
        try:
            res = subprocess.run(["docker", "logs", "--tail", "30", target], capture_output=True, text=True, timeout=15)
            logs = res.stdout if res.stdout else res.stderr
            if not logs:
                logs = "(no output)"
            telegram.send_direct(chat, f"📄 <b>Logs: {target}</b>\n<pre>{logs[-3500:]}</pre>")
        except Exception as e:
            telegram.send_direct(chat, f"❌ Error: {e}")
        return

    # --- Cancel button ---
    if action_type == "cancel":
        session.clear(uid)
        telegram.send_direct(chat, "👍 Cancelled.")
        return


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
    """Container management: status, restart, stop, start, inspect."""
    chat = msg["chat"]["id"]
    if not args:
        # Send interactive action menu
        buttons = _build_docker_menu()
        telegram.send_keyboard(
            chat,
            "🐳 <b>Docker Management</b>\n\nSelect an action:",
            buttons,
        )
        return

    cmd = args[0].lower()

    if cmd == "status":
        try:
            res = subprocess.run(["docker", "ps", "--format", "{{.Names}} | {{.Status}}"], capture_output=True, text=True, timeout=15)
            output = res.stdout.strip() if res.stdout else "No containers running."
            telegram.send_direct(chat, f"🐳 <b>Docker Status</b>\n<pre>{output}</pre>")
        except Exception as e:
            telegram.send_direct(chat, f"❌ Docker error: {e}")

    elif cmd in ("restart", "stop", "start"):
        if len(args) < 2:
            telegram.send_direct(chat, _fmt_container_list(f"Usage: <code>/docker {cmd} &lt;name&gt;</code>"))
            return
        target = args[1]
        allowed = get_allowed_containers()
        if target not in allowed:
            telegram.send_direct(chat, _fmt_container_list(f"🚫 <b>Access Denied</b>: '<code>{target}</code>' is not in the allowed list."))
            return
        verb = {"restart": "Restarting", "stop": "Stopping", "start": "Starting"}[cmd]
        emoji_ok = {"restart": "🔄", "stop": "🛑", "start": "▶️"}[cmd]
        telegram.send_direct(chat, f"⏳ {verb} <code>{target}</code>...")
        try:
            subprocess.run(["docker", cmd, target], check=True, timeout=60)
            telegram.send_direct(chat, f"{emoji_ok} Container <code>{target}</code> {cmd}ed successfully.")
        except Exception as e:
            telegram.send_direct(chat, f"❌ Failed to {cmd} <code>{target}</code>: {e}")

    elif cmd == "inspect":
        if len(args) < 2:
            telegram.send_direct(chat, _fmt_container_list(f"Usage: <code>/docker inspect &lt;name&gt;</code>"))
            return
        target = args[1]
        allowed = get_allowed_containers()
        if target not in allowed:
            telegram.send_direct(chat, _fmt_container_list(f"🚫 <b>Access Denied</b>: '<code>{target}</code>' is not in the allowed list."))
            return
        try:
            fmt = "{{.Config.Image}}|{{.State.Status}}|{{.State.StartedAt}}|{{.Created}}|{{.HostConfig.RestartPolicy.Name}}"
            res = subprocess.run(["docker", "inspect", "-f", fmt, target], capture_output=True, text=True, timeout=10)
            if res.returncode != 0:
                telegram.send_direct(chat, f"❌ Container <code>{target}</code> not found on this host.")
                return
            parts = res.stdout.strip().split("|")
            image, status, started, created, restart_pol = (parts + [""] * 5)[:5]
            # Get ports
            pres = subprocess.run(["docker", "inspect", "-f", "{{range $p, $c := .NetworkSettings.Ports}}{{$p}}->{{range $c}}{{.HostPort}}{{end}} {{end}}", target],
                                  capture_output=True, text=True, timeout=10)
            ports = pres.stdout.strip() or "none"
            info = (
                f"🔍 <b>Inspect: {target}</b>\n\n"
                f"  <b>Image:</b> <code>{image}</code>\n"
                f"  <b>Status:</b> {status}\n"
                f"  <b>Started:</b> <code>{started[:19]}</code>\n"
                f"  <b>Created:</b> <code>{created[:19]}</code>\n"
                f"  <b>Restart:</b> {restart_pol}\n"
                f"  <b>Ports:</b> <code>{ports}</code>"
            )
            telegram.send_direct(chat, info)
        except Exception as e:
            telegram.send_direct(chat, f"❌ Inspect error: {e}")
    else:
        telegram.send_direct(chat, f"❓ Unknown sub-command: <code>{cmd}</code>. Use /docker for help.")


def handle_logs(msg, args):
    """Fetches recent logs for a service."""
    if not args:
        # Send interactive container picker
        buttons = _build_container_keyboard("log")
        if buttons:
            buttons.append([{"text": "❌ Cancel", "callback_data": "cancel:0"}])
            telegram.send_keyboard(
                msg["chat"]["id"],
                "📄 <b>View Logs</b>\n\nSelect a service:",
                buttons,
            )
        else:
            telegram.send_direct(msg["chat"]["id"], "⚠️ No containers available for log viewing.")
        return

    target = args[0]
    allowed = get_allowed_containers()
    if target not in allowed:
         telegram.send_direct(msg["chat"]["id"], _fmt_container_list(f"🚫 Unauthorized or unknown service: '<code>{target}</code>'"))
         return

    try:
        res = subprocess.run(["docker", "logs", "--tail", "30", target], capture_output=True, text=True, timeout=15)
        logs = res.stdout if res.stdout else res.stderr
        if not logs:
            logs = "(no output)"
        telegram.send_direct(msg["chat"]["id"], f"📄 <b>Logs: {target}</b>\n<pre>{logs[-3500:]}</pre>")
    except Exception as e:
        telegram.send_direct(msg["chat"]["id"], f"❌ Error: {e}")


# --- New Command Handlers (v4.0) ---------------------------------------------

def _human_bytes(n):
    """Format bytes into a human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def handle_disk(msg):
    """Disk usage for key mount points."""
    chat = msg["chat"]["id"]
    lines = ["💾 <b>Disk Usage</b>\n"]
    data_dir = os.getenv("DATA_DIR", "/mnt")
    paths = {"/": "/", "DATA_DIR": data_dir}
    for label, path in paths.items():
        try:
            usage = shutil.disk_usage(path)
            pct = usage.used / usage.total * 100
            bar = "█" * int(pct // 10) + "░" * (10 - int(pct // 10))
            lines.append(
                f"  <b>{label}</b> (<code>{path}</code>)\n"
                f"  {bar} {pct:.1f}%\n"
                f"  {_human_bytes(usage.used)} / {_human_bytes(usage.total)} "
                f"({_human_bytes(usage.free)} free)\n"
            )
        except Exception as e:
            lines.append(f"  <b>{label}</b>: ❌ {e}\n")
    telegram.send_direct(chat, "\n".join(lines))


def handle_ip(msg):
    """Show public IP address."""
    chat = msg["chat"]["id"]
    try:
        req = urllib.request.Request("https://api.ipify.org", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            ip = resp.read().decode().strip()
        telegram.send_direct(chat, f"🌐 <b>Public IP:</b> <code>{ip}</code>")
    except Exception as e:
        telegram.send_direct(chat, f"❌ Could not determine public IP: {e}")


def handle_ports(msg):
    """List containers with their exposed ports."""
    chat = msg["chat"]["id"]
    try:
        res = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}} | {{.Ports}}"],
            capture_output=True, text=True, timeout=15,
        )
        if not res.stdout.strip():
            telegram.send_direct(chat, "🔌 No containers with exposed ports.")
            return
        telegram.send_direct(chat, f"🔌 <b>Exposed Ports</b>\n<pre>{res.stdout.strip()}</pre>")
    except Exception as e:
        telegram.send_direct(chat, f"❌ Error: {e}")


def handle_traefik(msg):
    """Traefik reverse proxy status and active routes."""
    chat = msg["chat"]["id"]
    lines = ["🔀 <b>Traefik Status</b>\n"]
    # 1. Container status
    try:
        res = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Status}}|{{.State.StartedAt}}", "traefik"],
            capture_output=True, text=True, timeout=10,
        )
        if res.returncode == 0:
            parts = res.stdout.strip().split("|")
            status, started = parts[0], parts[1][:19] if len(parts) > 1 else "?"
            emoji = "✅" if status == "running" else "❌"
            lines.append(f"  {emoji} Container: <b>{status}</b> (since <code>{started}</code>)\n")
        else:
            lines.append("  ❌ Traefik container not found\n")
            telegram.send_direct(chat, "\n".join(lines))
            return
    except Exception as e:
        lines.append(f"  ❌ Inspect error: {e}\n")
        telegram.send_direct(chat, "\n".join(lines))
        return

    # 2. Active routes from container labels
    try:
        res = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}|{{.Label \"traefik.http.routers\"}}|{{.Label \"traefik.enable\"}}"],
            capture_output=True, text=True, timeout=10,
        )
        routes = []
        for line in (res.stdout or "").strip().splitlines():
            parts = line.split("|")
            name = parts[0]
            enabled = parts[2].strip().lower() if len(parts) > 2 else ""
            if enabled == "true":
                routes.append(f"  • <code>{name}</code>")
        if routes:
            lines.append(f"\n📡 <b>Traefik-enabled services:</b> ({len(routes)})\n" + "\n".join(routes))
        else:
            lines.append("\n  ⚠️ No Traefik-enabled services detected.")
    except Exception:
        pass

    telegram.send_direct(chat, "\n".join(lines))


def handle_resources(msg):
    """CPU, RAM, and container resource usage from existing metrics agent data."""
    chat = msg["chat"]["id"]
    lines = ["📊 <b>System Resources</b>\n"]

    # System metrics from metrics.json (already collected by metrics agent)
    try:
        data = json.loads(METRICS_JSON.read_text()) if METRICS_JSON.exists() else {}
        sys_m = data.get("system", {})
        cpu = sys_m.get("cpu", 0)
        mem = sys_m.get("mem", 0)
        cpu_bar = "█" * int(cpu // 10) + "░" * (10 - int(cpu // 10))
        mem_bar = "█" * int(mem // 10) + "░" * (10 - int(mem // 10))
        lines.append(f"  <b>CPU:</b> {cpu_bar} {cpu:.1f}%")
        lines.append(f"  <b>RAM:</b> {mem_bar} {mem:.1f}%\n")

        containers = data.get("containers", [])
        if containers:
            lines.append(f"  <b>Top Containers:</b>")
            for c in sorted(containers, key=lambda x: x.get("cpu", 0), reverse=True)[:8]:
                lines.append(f"    <code>{c['name']:25}</code> CPU: {c.get('cpu', 0):5.1f}%  MEM: {c.get('mem_usage', 'N/A')}")
        else:
            lines.append("  ⚠️ No container stats available.")
    except Exception as e:
        lines.append(f"  ❌ Metrics read error: {e}")

    # Health score
    try:
        report = json.loads(HEALTH_REPORT_JSON.read_text()) if HEALTH_REPORT_JSON.exists() else {}
        score = report.get("score", "?")
        verdict = report.get("verdict", "UNKNOWN")
        lines.append(f"\n  🏥 Health: <b>{verdict}</b> ({score}%)")
    except Exception:
        pass

    telegram.send_direct(chat, "\n".join(lines))


def handle_reboot(msg, args):
    """Reboot the host (requires 'confirm' keyword)."""
    chat = msg["chat"]["id"]
    if sys.platform == "win32":
        telegram.send_direct(chat, "⚠️ Reboot is only supported on Linux production hosts.")
        return
    if not args or args[0].lower() != "confirm":
        telegram.send_direct(chat, "⚠️ <b>Reboot requires confirmation.</b>\n\nSend <code>/reboot confirm</code> to reboot the host.")
        return
    telegram.send_direct(chat, "🔄 <b>Rebooting host in 5 seconds...</b>")
    time.sleep(5)
    try:
        subprocess.run(["reboot"], check=True, timeout=10)
    except Exception as e:
        telegram.send_direct(chat, f"❌ Reboot failed: {e}")


def handle_update(msg, args):
    """Pull latest images and recreate containers (requires 'confirm')."""
    chat = msg["chat"]["id"]
    if not args or args[0].lower() != "confirm":
        telegram.send_direct(chat, "⚠️ <b>Update requires confirmation.</b>\n\nSend <code>/update confirm</code> to pull and restart all stacks.")
        return

    telegram.send_direct(chat, "⬇️ <b>Pulling latest images...</b> This may take a few minutes.")
    # Find compose files under docker/
    compose_dirs = []
    if DOCKER_DIR.exists():
        for child in DOCKER_DIR.iterdir():
            if child.is_dir():
                for cf in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
                    if (child / cf).exists():
                        compose_dirs.append(child)
                        break

    if not compose_dirs:
        telegram.send_direct(chat, "⚠️ No compose stacks found under <code>docker/</code>.")
        return

    results = []
    for cdir in compose_dirs:
        stack = cdir.name
        try:
            subprocess.run(["docker", "compose", "pull"], cwd=str(cdir), check=True, timeout=300, capture_output=True)
            subprocess.run(["docker", "compose", "up", "-d"], cwd=str(cdir), check=True, timeout=120, capture_output=True)
            results.append(f"  ✅ {stack}")
        except Exception as e:
            results.append(f"  ❌ {stack}: {e}")

    telegram.send_direct(chat, "📦 <b>Update Results</b>\n\n" + "\n".join(results))


def handle_backup(msg):
    """Trigger a config backup using the existing backup script."""
    chat = msg["chat"]["id"]
    telegram.send_direct(chat, "💾 <b>Starting backup...</b>")
    try:
        # Import and call the existing backup function
        backup_script = REPO_ROOT / "scripts" / "maintenance" / "backup.py"
        if not backup_script.exists():
            telegram.send_direct(chat, "❌ Backup script not found.")
            return
        # Run as subprocess to isolate
        res = subprocess.run(
            [sys.executable, str(backup_script)],
            capture_output=True, text=True, timeout=120,
        )
        output = (res.stdout + res.stderr).strip()
        if res.returncode == 0:
            telegram.send_direct(chat, f"✅ <b>Backup complete</b>\n<pre>{output[-2000:]}</pre>")
        else:
            telegram.send_direct(chat, f"❌ <b>Backup failed</b>\n<pre>{output[-2000:]}</pre>")
    except Exception as e:
        telegram.send_direct(chat, f"❌ Backup error: {e}")


def handle_mute(msg, unmute=False):
    """Mute or unmute proactive alerts."""
    chat = msg["chat"]["id"]
    if unmute:
        try:
            if MUTE_STATE_JSON.exists():
                MUTE_STATE_JSON.unlink()
            telegram.send_direct(chat, "🔔 <b>Alerts resumed.</b> Proactive notifications are active.")
        except Exception as e:
            telegram.send_direct(chat, f"❌ Unmute error: {e}")
        return

    # Mute for 1 hour by default
    uid = msg.get("from", {}).get("id", 0)
    until = int(time.time()) + 3600
    state = {"muted": True, "until": until, "by": uid}
    try:
        MUTE_STATE_JSON.write_text(json.dumps(state))
        telegram.send_direct(chat, "🔇 <b>Alerts muted for 1 hour.</b>\nSend /unmute to resume early.")
    except Exception as e:
        telegram.send_direct(chat, f"❌ Mute error: {e}")


def handle_who(msg):
    """Show allowed Telegram user IDs."""
    chat = msg["chat"]["id"]
    if not ALLOWED_USERS:
        telegram.send_direct(chat, "🔓 <b>Access: OPEN</b>\n\nNo ALLOWED_USERS configured — any user can send commands.")
        return
    user_lines = "\n".join(f"  • <code>{uid}</code>" for uid in ALLOWED_USERS)
    telegram.send_direct(chat, f"🔐 <b>Allowed Users</b> ({len(ALLOWED_USERS)})\n\n{user_lines}")


def handle_env(msg):
    """Show environment config with sensitive values masked."""
    chat = msg["chat"]["id"]
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        telegram.send_direct(chat, "❌ .env file not found.")
        return

    SENSITIVE = ("TOKEN", "SECRET", "KEY", "PASSWORD", "PASS", "HASH")

    def _mask(val):
        if not val or len(val) <= 4:
            return "***"
        return val[:2] + "***" + val[-2:]

    try:
        lines = ["⚙️ <b>Environment Config</b>\n<pre>"]
        with open(env_file, "r") as f:
            for raw in f:
                raw = raw.strip()
                if not raw or raw.startswith("#"):
                    continue
                if "=" not in raw:
                    continue
                if raw.startswith("export "):
                    raw = raw[7:].strip()
                k, v = raw.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if any(s in k.upper() for s in SENSITIVE):
                    v = _mask(v)
                lines.append(f"  {k}={v}")
        lines.append("</pre>")
        text = "\n".join(lines)
        # Telegram message limit ~4096 chars
        if len(text) > 3900:
            text = text[:3900] + "\n... (truncated)</pre>"
        telegram.send_direct(chat, text)
    except Exception as e:
        telegram.send_direct(chat, f"❌ Error reading .env: {e}")



# --- Core Loop ----------------------------------------------------------------

def process_update(update):
    # --- Callback Query (inline keyboard button press) ---
    if "callback_query" in update:
        handle_callback(update["callback_query"])
        return

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
    elif cmd == "/uptime":
        uptime = str(datetime.now() - START_TIME).split(".")[0]
        telegram.send_direct(msg["chat"]["id"], f"Uptime: <code>{uptime}</code>")

    # --- Docker / Infrastructure ---
    elif cmd == "/disk":
        handle_disk(msg)

    # --- Networking ---
    elif cmd == "/ip":
        handle_ip(msg)
    elif cmd == "/ports":
        handle_ports(msg)
    elif cmd == "/traefik":
        handle_traefik(msg)

    # --- System ---
    elif cmd == "/resources":
        handle_resources(msg)
    elif cmd == "/reboot":
        handle_reboot(msg, args)
    elif cmd == "/update":
        handle_update(msg, args)
    elif cmd == "/backup":
        handle_backup(msg)

    # --- Bot Management ---
    elif cmd == "/mute":
        handle_mute(msg)
    elif cmd == "/unmute":
        handle_mute(msg, unmute=True)
    elif cmd == "/who":
        handle_who(msg)
    elif cmd == "/env":
        handle_env(msg)

    elif cmd in ("/help", "/start", "/menu"):
        send_main_menu(msg["chat"]["id"])


def listen_loop(initial_offset):
    offset = initial_offset
    
    pulse_count = 0
    last_health_update = 0
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

        # Heartbeat: keep health timestamp fresh so health_score doesn't
        # flag this agent as stalled (listen_loop never returns to wrap_agent)
        now = time.time()
        if now - last_health_update > 60:
            try:
                from utils.guards import update_agent_health
                update_agent_health("command_listener", success=True)
            except Exception:
                pass
            last_health_update = now
            
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
