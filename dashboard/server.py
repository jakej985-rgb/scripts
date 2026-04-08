import os
import json
import secrets
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_socketio import SocketIO, emit
from functools import wraps
import bcrypt
import eventlet

# AUTO-ROOT pattern for path safety
def get_repo_root():
    import subprocess
    try:
        return subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], 
                                     stderr=subprocess.DEVNULL).decode('utf-8').strip()
    except:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REPO_ROOT = get_repo_root()
STATE_DIR = os.path.join(REPO_ROOT, "control-plane", "state")
USERS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")

# Core state paths
HEALTH_JSON = os.path.join(STATE_DIR, "health.json")
METRICS_JSON = os.path.join(STATE_DIR, "metrics.json")
ANOMALIES_JSON = os.path.join(STATE_DIR, "anomalies.json")
DECISIONS_JSON = os.path.join(STATE_DIR, "decisions.json")
REGISTRY_JSON = os.path.join(STATE_DIR, "registry.json")

# Historical metrics (Batch 4 T8)
METRICS_HISTORY_CSV = os.path.join(STATE_DIR, "metrics-history.csv")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("DASHBOARD_SECRET", secrets.token_hex(32))
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

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

def load_users():
    if not os.path.exists(USERS_JSON):
        return []
    try:
        with open(USERS_JSON, 'r') as f:
            return json.load(f)
    except:
        return []

def load_json_safe(path, default=None):
    if default is None: default = {}
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except:
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
        username = request.form.get('username')
        password = request.form.get('password')
        
        users = load_users()
        user = next((u for u in users if u['username'] == username), None)
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user['token_hash'].encode('utf-8')):
            session['username'] = username
            session['role'] = user.get('role', 'viewer')
            return redirect(url_for('index'))
            
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

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

@app.route('/api/metrics/history')
@login_required()
def get_metrics_history():
    """Batch 4 T8: Highly optimized tail strategy for metrics history."""
    if not os.path.exists(METRICS_HISTORY_CSV):
        return jsonify([])
    
    try:
        # Use tail command via subprocess (fastest way to read end of large CSV)
        import subprocess
        # Get last 200 entries
        output = subprocess.check_output(['tail', '-n', '200', METRICS_HISTORY_CSV], 
                                       stderr=subprocess.DEVNULL).decode('utf-8')
        
        results = []
        for line in output.splitlines():
            parts = line.strip().split(',')
            if len(parts) >= 3:
                results.append({
                    "timestamp": parts[0],
                    "cpu": float(parts[1]),
                    "mem": float(parts[2])
                })
        return jsonify(results)
    except:
        return jsonify([])

# -------------------------------
# WEBSOCKET STREAM (Real-time)
# -------------------------------

@socketio.on('connect')
def handle_connect():
    emit('status', {'msg': 'Connected to M3TAL Control Plane'})

def background_metrics_stream():
    """Push real-time metric updates to all connected clients."""
    while True:
        socketio.sleep(2)
        metrics = load_json_safe(METRICS_JSON)
        socketio.emit('metrics_update', metrics)

# Start background stream in eventlet
eventlet.spawn(background_metrics_stream)

if __name__ == '__main__':
    port = int(os.getenv("DASHBOARD_PORT", 8080))
    # Using eventlet for WebSocket support
    socketio.run(app, host='0.0.0.0', port=port)
