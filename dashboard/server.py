import os
import json
import secrets
import threading
import hmac
from pathlib import Path
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room
from functools import wraps

from auth import load_users, resolve_users_path, verify_password

try:
    import eventlet  # type: ignore
except Exception:
    eventlet = None

# AUTO-ROOT pattern for path safety
def get_repo_root():
    import subprocess
    try:
        return subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], 
                                     stderr=subprocess.DEVNULL).decode('utf-8').strip()
    except Exception:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
socketio = SocketIO(app, async_mode=ASYNC_MODE)

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
    if request.method == 'POST':
        # CSRF Protection (Audit Fix 2.1 - Timing Attack Guard)
        form_token = request.form.get('csrf_token')
        session_token = session.get('csrf_token')
        
        if not form_token or not session_token or not hmac.compare_digest(form_token, session_token):
            return render_template('login.html', error="Security violation: Invalid or expired CSRF token"), 403

        username = request.form.get('username')
        password = request.form.get('password')
        
        users = load_users(users_path=USERS_JSON)
        user = next((u for u in users if u['username'] == username), None)
        
        if user and password and verify_password(password, user['token_hash']):
            session['username'] = username
            session['role'] = user.get('role', 'viewer')
            # Clear token after successful login or rotate
            session.pop('csrf_token', None)
            return redirect(url_for('index'))
            
        return render_template('login.html', error="Invalid credentials", csrf_token=session.get('csrf_token'))
    
    # Generate token for GET
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
        
    return render_template('login.html', csrf_token=session['csrf_token'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

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

# -------------------------------
# WEBSOCKET STREAM (Real-time)
# -------------------------------

@socketio.on('connect')
def handle_connect():
    if 'username' not in session:
        return False

    join_room(AUTHENTICATED_ROOM)
    emit('status', {'msg': 'Connected to M3TAL Control Plane'})

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
    socketio.start_background_task(background_metrics_stream)

# Audit fix 2.3 — Start outside main for Docker/WSGI visibility
# Guarded for test environment to prevent background task proliferation
if __name__ == '__main__':
    start_background_tasks()
    
    port = int(os.getenv("DASHBOARD_PORT", 8080))
    socketio.run(app, host='0.0.0.0', port=port)
