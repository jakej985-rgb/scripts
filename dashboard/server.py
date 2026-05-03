import os
try:
    import eventlet
    eventlet.monkey_patch()
except ImportError:
    pass

import json
import secrets
import threading
import hmac
from pathlib import Path
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room
from functools import wraps

import sys
import traceback
import logging

# Configure verbose logging for the whole app
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)
logger = logging.getLogger("m3tal-dashboard")

# Global catch-all for absolutely any crash
def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("❌ UNHANDLED FATAL EXCEPTION", exc_info=(exc_type, exc_value, exc_traceback))
    print("="*60, flush=True)
    print(" 🚨 GLOBAL CRASH DETECTED 🚨", flush=True)
    print(f" ERROR: {exc_value}", flush=True)
    traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stdout)
    print("="*60, flush=True)

sys.excepthook = global_exception_handler

from auth import load_users, resolve_users_path, verify_password
try:
    import eventlet  # type: ignore
except Exception:
    eventlet = None

# AUTO-ROOT pattern for path safety
def get_repo_root():
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / ".env").exists() and (parent / "docker").exists():
            return str(parent)
    return str(Path(__file__).resolve().parent.parent)

REPO_ROOT = get_repo_root()
STATE_DIR = os.getenv("STATE_DIR") or os.path.join(REPO_ROOT, "control-plane", "state")
USERS_JSON = os.fspath(resolve_users_path(Path(__file__).resolve().parent))
ASYNC_MODE = "eventlet" if eventlet is not None else "threading"
AUTHENTICATED_ROOM = "authenticated-clients"

# Core state paths
HEALTH_JSON = os.path.join(STATE_DIR, "health.json")
METRICS_JSON = os.path.join(STATE_DIR, "metrics.json")
ANOMALIES_JSON = os.path.join(STATE_DIR, "anomalies.json")
DECISIONS_JSON = os.path.join(STATE_DIR, "decisions.json")
REGISTRY_JSON = os.path.join(STATE_DIR, "registry.json")
HEALTH_REPORT_JSON = os.path.join(STATE_DIR, "health_report.json")

# Historical metrics (Batch 4 T8)
METRICS_HISTORY_CSV = os.path.join(STATE_DIR, "metrics-history.csv")

app = Flask(__name__)
# Audit Fix 2.4: Fail fast if SECRET_KEY is missing to ensure session persistence
DASHBOARD_SECRET = os.getenv("DASHBOARD_SECRET")
if not DASHBOARD_SECRET:
    print("❌ [SECURITY] CRITICAL: DASHBOARD_SECRET environment variable is not set.")
    print("Session persistence and CSRF security are compromised. Generating ephemeral key...")
    DASHBOARD_SECRET = secrets.token_hex(32)

app.config['SECRET_KEY'] = DASHBOARD_SECRET
socketio = SocketIO(app, async_mode=ASYNC_MODE, cors_allowed_origins="*")

# Simple Role-Based Access Control (Batch 3 T1)
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                return redirect(url_for('login', next=request.url))
            if role and session.get('role') != role and session.get('role') != 'admin':
                return jsonify({"error": "Unauthorized"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def load_json_safe(path, default=None):
    if default is None: default = {}
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return default

# -------------------------------
# ROUTES
# -------------------------------

@app.route('/')
@login_required()
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Ensure session has a token
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)

    if request.method == 'POST':
        # CSRF Protection
        form_token = request.form.get('csrf_token')
        session_token = session.get('csrf_token')
        
        if not form_token or not session_token or not hmac.compare_digest(form_token, session_token):
            print(f"❌ CSRF Failure! Form token: '{form_token}', Session token: '{session_token}'", flush=True)
            return render_template('login.html', error="Security violation: Invalid or expired CSRF token", csrf_token=session['csrf_token']), 403

        username = request.form.get('username')
        password = request.form.get('password')
        
        users = load_users(users_path=USERS_JSON)
        user = next((u for u in users if u['username'] == username), None)
        
        if user and password and verify_password(password, user['token_hash']):
            session['username'] = username
            session['role'] = user.get('role', 'viewer')
            session.pop('csrf_token', None)
            return redirect(url_for('index'))
            
        return render_template('login.html', error="Invalid credentials", csrf_token=session['csrf_token'])
    
    return render_template('login.html', csrf_token=session['csrf_token'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/fleet')
@login_required()
def fleet():
    return render_template('fleet.html')

@app.route('/intelligence')
@login_required()
def intelligence():
    return render_template('intelligence.html')

@app.route('/logs')
@login_required()
def logs():
    return render_template('logs.html')

# -------------------------------
# API ENDPOINTS
# -------------------------------

@app.route('/api/health')
@login_required()
def get_health():
    return jsonify(load_json_safe(HEALTH_JSON))

@app.route('/api/health/report')
@login_required()
def get_health_report():
    """Returns the full health score and verdict report (Audit fix 6.6 — C1)"""
    return jsonify(load_json_safe(HEALTH_REPORT_JSON))


@app.route('/api/metrics')
@login_required()
def get_metrics():
    return jsonify(load_json_safe(METRICS_JSON))

@app.route('/api/anomalies')
@login_required()
def get_anomalies():
    return jsonify(load_json_safe(ANOMALIES_JSON))

@app.route('/api/registry')
@login_required()
def get_registry():
    return jsonify(load_json_safe(REGISTRY_JSON))

@app.route('/api/decisions')
@login_required()
def get_decisions():
    return jsonify(load_json_safe(DECISIONS_JSON))

@app.route('/api/logs')
@login_required()
def get_logs():
    logs_dir = os.path.join(STATE_DIR, "logs")
    log_data = {}
    if os.path.exists(logs_dir):
        try:
            for filename in os.listdir(logs_dir):
                if filename.endswith(".log"):
                    filepath = os.path.join(logs_dir, filename)
                    try:
                        from collections import deque
                        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                            # Tail the last 100 lines of each log
                            lines = list(deque(f, maxlen=100))
                            log_data[filename] = "".join(lines)
                    except Exception as e:
                        log_data[filename] = f"[Error reading file: {e}]"
        except Exception as e:
            pass
    return jsonify(log_data)

@app.route('/healthz')
def health_check():
    """Liveness probe for external uptime monitors (Batch 16 T2)"""
    return jsonify({"status": "ready", "version": "1.3.0"}), 200

@app.route('/api/metrics/history')
@login_required()
def get_metrics_history():
    """Batch 4 T8: Highly optimized tail strategy for metrics history."""
    if not os.path.exists(METRICS_HISTORY_CSV):
        return jsonify([])
    
    try:
        from collections import deque
        with open(METRICS_HISTORY_CSV, 'r') as f:
            # Efficiently tail the last 200 lines
            recent = deque(f, maxlen=200)
        
        results = []
        for line in recent:
            if line.startswith('timestamp,'): continue
            parts = line.strip().split(',')

            # CSV format: timestamp,name,cpu,mem (4 columns — Audit fix 2.7)
            if len(parts) >= 4:
                try:
                    results.append({
                        "timestamp": parts[0],
                        "name": parts[1],
                        "cpu": float(parts[2]),
                        "mem": float(parts[3])
                    })
                except (ValueError, IndexError):
                    continue
        return jsonify(results)
    except Exception:
        return jsonify([])

# --- Action API (Dashboard Buttons) -------------------------------------------

import subprocess as _sp
import re as _re

# Whitelist of allowed container actions to prevent injection
_CONTAINER_ACTIONS = {"restart", "stop", "start"}
# Sanitize container names — only allow alphanumeric, dash, underscore, dot
_SAFE_NAME = _re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$')

def _audit_log(action, target, user, result):
    """Log all dashboard actions for traceability."""
    logger.info(f"[ACTION] user={user} action={action} target={target} result={result}")

@app.route('/api/action', methods=['POST'])
@login_required()
def api_action():
    """Execute container or global actions from the dashboard UI."""
    data = request.get_json(silent=True) or {}
    action = (data.get('action') or '').strip().lower()
    container = (data.get('container') or '').strip()
    user = session.get('username', 'unknown')

    if not action:
        return jsonify({"ok": False, "error": "Missing 'action' field"}), 400

    # ── Container-scoped actions ──────────────────────────────────
    if container:
        if action not in _CONTAINER_ACTIONS:
            return jsonify({"ok": False, "error": f"Unknown container action: {action}"}), 400

        if not _SAFE_NAME.match(container):
            return jsonify({"ok": False, "error": "Invalid container name"}), 400

        try:
            proc = _sp.run(
                ["docker", action, container],
                capture_output=True, text=True, timeout=60
            )
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "Unknown error").strip()
                _audit_log(action, container, user, f"FAIL: {err}")
                return jsonify({"ok": False, "error": err}), 500

            _audit_log(action, container, user, "OK")
            return jsonify({"ok": True, "message": f"{action} on {container} succeeded"})
        except _sp.TimeoutExpired:
            _audit_log(action, container, user, "TIMEOUT")
            return jsonify({"ok": False, "error": f"Timed out after 60s"}), 504
        except Exception as e:
            _audit_log(action, container, user, f"ERROR: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    # ── Container logs (returns log text, not an action) ──────────
    if action == "logs":
        target = (data.get('target') or '').strip()
        if not target or not _SAFE_NAME.match(target):
            return jsonify({"ok": False, "error": "Invalid container name for logs"}), 400
        try:
            proc = _sp.run(
                ["docker", "logs", "--tail", "80", target],
                capture_output=True, text=True, timeout=15
            )
            output = proc.stdout or proc.stderr or "(no output)"
            return jsonify({"ok": True, "logs": output[-8000:]})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    # ── Global actions ────────────────────────────────────────────
    if action == "status":
        report = load_json_safe(HEALTH_REPORT_JSON)
        health = load_json_safe(HEALTH_JSON)
        _audit_log("status", "global", user, "OK")
        return jsonify({
            "ok": True,
            "score": report.get("score", 0),
            "verdict": report.get("verdict", "Unknown"),
            "mode": report.get("mode", "unknown"),
            "issues": report.get("issues", []),
            "system": health.get("status", "unknown"),
        })

    if action == "heal":
        _audit_log("heal", "all", user, "STARTED")
        try:
            # Trigger the init.py repair function in a subprocess
            repair_script = os.path.join(REPO_ROOT, "control-plane", "init.py")
            if not os.path.exists(repair_script):
                return jsonify({"ok": False, "error": "Repair script not found"}), 500

            proc = _sp.run(
                [sys.executable, repair_script, "--repair=all"],
                capture_output=True, text=True, timeout=300,
                cwd=os.path.join(REPO_ROOT, "control-plane")
            )
            result = "OK" if proc.returncode == 0 else f"EXIT {proc.returncode}"
            _audit_log("heal", "all", user, result)
            return jsonify({
                "ok": proc.returncode == 0,
                "message": "Heal cycle completed" if proc.returncode == 0 else "Heal encountered errors",
                "output": (proc.stdout or "")[-2000:]
            })
        except _sp.TimeoutExpired:
            _audit_log("heal", "all", user, "TIMEOUT")
            return jsonify({"ok": False, "error": "Heal timed out after 5 minutes"}), 504
        except Exception as e:
            _audit_log("heal", "all", user, f"ERROR: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    if action == "scan":
        _audit_log("scan", "all", user, "STARTED")
        # Trigger a health score recalculation
        try:
            scorer_script = os.path.join(REPO_ROOT, "control-plane", "agents", "health_score.py")
            if os.path.exists(scorer_script):
                _sp.run(
                    [sys.executable, scorer_script, "--once"],
                    capture_output=True, text=True, timeout=30,
                    cwd=os.path.join(REPO_ROOT, "control-plane")
                )
            # Return fresh report
            report = load_json_safe(HEALTH_REPORT_JSON)
            _audit_log("scan", "all", user, "OK")
            return jsonify({
                "ok": True,
                "score": report.get("score", 0),
                "verdict": report.get("verdict", "Unknown"),
                "issues": report.get("issues", []),
            })
        except Exception as e:
            _audit_log("scan", "all", user, f"ERROR: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    if action == "reboot":
        # Admin-only, Linux-only
        if session.get('role') != 'admin':
            return jsonify({"ok": False, "error": "Reboot requires admin role"}), 403
        if sys.platform == "win32":
            return jsonify({"ok": False, "error": "Reboot is only supported on Linux hosts"}), 400
        _audit_log("reboot", "host", user, "INITIATED")
        try:
            _sp.Popen(["bash", "-c", "sleep 5 && reboot"])
            return jsonify({"ok": True, "message": "Host rebooting in 5 seconds..."})
        except Exception as e:
            _audit_log("reboot", "host", user, f"ERROR: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": False, "error": f"Unknown action: {action}"}), 400


# -------------------------------
# WEBSOCKET STREAM (Real-time)
# -------------------------------

@socketio.on('connect')
def handle_connect(auth=None):
    # 🛡️ SECURITY FIX: Re-enforcing authentication check (Audit C2)
    if 'username' not in session:
        return False

    join_room(AUTHENTICATED_ROOM)
    emit('status', {'msg': 'Connected to M3TAL Control Plane'})

    # Start background tasks if not already running
    global background_thread, _bg_started
    with _bg_lock:
        if not _bg_started or background_thread is None:
            start_background_tasks()
            _bg_started = True
        elif hasattr(background_thread, 'is_alive') and not background_thread.is_alive():
            # If the thread died, restart it
            start_background_tasks()

def emit_metrics_update():
    metrics = load_json_safe(METRICS_JSON)
    socketio.emit('metrics_update', metrics, to=AUTHENTICATED_ROOM)

def background_metrics_stream():
    """Push real-time metric updates to all connected clients."""
    while True:
        try:
            socketio.sleep(2)
            emit_metrics_update()
        except Exception as e:
            print(f"[DASHBOARD] Background metrics error: {e}")
            socketio.sleep(5)


def start_background_tasks():
    """Initialize background workers for SocketIO."""
    global background_thread
    background_thread = socketio.start_background_task(background_metrics_stream)

_bg_started = False
background_thread = None
_bg_lock = threading.Lock()

if __name__ == '__main__':
    # Audit Fix C1: Dashboard binds to 127.0.0.1 to avoid unencrypted external exposure.
    # External access should be through Traefik or a secure tunnel.
    host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("DASHBOARD_PORT", 8080))
    
    print("="*50)
    print(" 🚀 M3TAL DASHBOARD STARTING...")
    print(f" 🌐 Binding to: http://{host}:{port}")
    print(f" 🧵 Async Mode: {ASYNC_MODE}")
    print("="*50)
    
    try:
        socketio.run(app, host=host, port=port)
    except Exception as e:
        print("="*50)
        print(" ❌ FATAL ERROR DURING STARTUP")
        print(f" {e}")
        import traceback
        traceback.print_exc()
        print("="*50)
        import sys
        sys.exit(1)
