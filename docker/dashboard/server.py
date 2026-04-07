from flask import Flask, render_template, jsonify, request, redirect, Response, abort
from functools import wraps
import subprocess
import csv
import json
import os
import time

app = Flask(__name__)

STATE = "/docker/state"
LOGS = "/docker/logs"
USERS_FILE = "/docker/dashboard/users.json"
NODES_FILE = "/docker/nodes.json"

# ── Helpers ──

def read_file(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return f.readlines()

def read_retries():
    retries = {}
    retries_dir = os.path.join(STATE, "retries")
    if os.path.isdir(retries_dir):
        for name in os.listdir(retries_dir):
            if name.startswith("."): continue
            path = os.path.join(retries_dir, name)
            try:
                with open(path) as f:
                    retries[name] = int(f.read().strip())
            except (ValueError, IOError):
                retries[name] = 0
    return retries

def read_cooldowns():
    cooldowns = {}
    cd_dir = os.path.join(STATE, "cooldowns")
    if os.path.isdir(cd_dir):
        for name in os.listdir(cd_dir):
            if name.startswith("."): continue
            path = os.path.join(cd_dir, name)
            try:
                with open(path) as f:
                    ts = int(f.read().strip())
                    cooldowns[name] = int(time.time()) - ts
            except (ValueError, IOError):
                cooldowns[name] = -1
    return cooldowns

# ── v4.2: RBAC Auth ──

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE) as f:
        return json.load(f)

def check_auth(username, password):
    users = load_users()
    if not users:
        return True  # No users file = open access (dev mode)
    return username in users and users[username]["password"] == password

def get_role(username):
    users = load_users()
    if not users:
        return "admin"
    if username in users:
        return users[username]["role"]
    return "viewer"

def authenticate():
    return Response(
        "Authentication required", 401,
        {"WWW-Authenticate": 'Basic realm="M3TAL Control Plane"'}
    )

def requires_auth(role_required=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth = request.authorization
            if not auth or not check_auth(auth.username, auth.password):
                return authenticate()
            if role_required:
                role = get_role(auth.username)
                role_hierarchy = {"admin": 3, "operator": 2, "viewer": 1}
                if role_hierarchy.get(role, 0) < role_hierarchy.get(role_required, 0):
                    return abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ── Routes: Dashboard ──

@app.route("/")
@requires_auth("viewer")
def index():
    containers = read_file(f"{STATE}/containers.txt")
    analysis = read_file(f"{STATE}/analysis.txt")
    actions = read_file(f"{STATE}/actions.txt")
    disk = read_file(f"{STATE}/disk.txt")
    logs = read_file(f"{LOGS}/actions.log")[-50:]
    retries = read_retries()
    cooldowns = read_cooldowns()
    ai_recs = read_file(f"{STATE}/ai-recommendations.txt")
    anomalies = read_file(f"{STATE}/anomalies.txt")
    deps = read_file(f"{STATE}/dependency-issues.txt")
    metrics = read_file(f"{STATE}/metrics.txt")

    return render_template("index.html",
        containers=containers,
        analysis=analysis,
        actions=actions,
        disk=disk,
        logs=logs,
        retries=retries,
        cooldowns=cooldowns,
        ai_recs=ai_recs,
        anomalies=anomalies,
        deps=deps,
        metrics=metrics,
    )

# ── Routes: JSON API ──

@app.route("/api/state")
@requires_auth("viewer")
def api_state():
    containers = read_file(f"{STATE}/containers.txt")
    analysis = read_file(f"{STATE}/analysis.txt")
    actions = read_file(f"{STATE}/actions.txt")
    disk = read_file(f"{STATE}/disk.txt")
    logs = read_file(f"{LOGS}/actions.log")[-50:]
    retries = read_retries()
    cooldowns = read_cooldowns()
    ai_recs = read_file(f"{STATE}/ai-recommendations.txt")
    anomalies = read_file(f"{STATE}/anomalies.txt")
    deps = read_file(f"{STATE}/dependency-issues.txt")
    metrics = read_file(f"{STATE}/metrics.txt")

    return jsonify({
        "containers": [l.strip() for l in containers],
        "analysis": [l.strip() for l in analysis],
        "actions": [l.strip() for l in actions],
        "disk": [l.strip() for l in disk],
        "logs": [l.strip() for l in logs],
        "retries": retries,
        "cooldowns": cooldowns,
        "ai_recs": [l.strip() for l in ai_recs],
        "anomalies": [l.strip() for l in anomalies],
        "deps": [l.strip() for l in deps],
        "metrics": [l.strip() for l in metrics],
        "timestamp": int(time.time()),
    })

# ── v4: Container Control ──

@app.route("/api/restart/<name>", methods=["POST"])
@requires_auth("operator")
def restart(name):
    subprocess.run(["docker", "restart", name])
    with open(f"{LOGS}/actions.log", "a") as f:
        f.write(f"{time.strftime('%c')} Dashboard: Restarted {name}\n")
    return jsonify({"status": "ok", "action": "restart", "container": name})

@app.route("/api/stop/<name>", methods=["POST"])
@requires_auth("operator")
def stop(name):
    subprocess.run(["docker", "stop", name])
    with open(f"{LOGS}/actions.log", "a") as f:
        f.write(f"{time.strftime('%c')} Dashboard: Stopped {name}\n")
    return jsonify({"status": "ok", "action": "stop", "container": name})

@app.route("/api/start/<name>", methods=["POST"])
@requires_auth("operator")
def start(name):
    subprocess.run(["docker", "start", name])
    with open(f"{LOGS}/actions.log", "a") as f:
        f.write(f"{time.strftime('%c')} Dashboard: Started {name}\n")
    return jsonify({"status": "ok", "action": "start", "container": name})

@app.route("/api/approve", methods=["POST"])
@requires_auth("admin")
def approve():
    subprocess.run(["/docker/agents/action-agent.sh", "force"])
    with open(f"{LOGS}/actions.log", "a") as f:
        f.write(f"{time.strftime('%c')} Dashboard: Force-approved pending actions\n")
    return jsonify({"status": "ok", "action": "approve"})

# ── v4.1: Metrics Time-Series ──

@app.route("/api/metrics/<name>")
@requires_auth("viewer")
def metrics_api(name):
    history = f"{STATE}/metrics-history.csv"
    data = []
    if os.path.exists(history):
        with open(history) as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 4: continue
                ts, container, cpu, mem = row[0], row[1], row[2], row[3]
                if container == name:
                    try:
                        data.append({
                            "time": int(ts),
                            "cpu": float(cpu),
                            "mem": float(mem)
                        })
                    except ValueError:
                        continue
    return jsonify(data[-100:])

@app.route("/api/metrics/containers")
@requires_auth("viewer")
def metrics_container_list():
    history = f"{STATE}/metrics-history.csv"
    names = set()
    if os.path.exists(history):
        with open(history) as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    names.add(row[1])
    return jsonify(sorted(names))

# ── v5: Cluster ──

@app.route("/api/cluster")
@requires_auth("viewer")
def cluster_status():
    if not os.path.exists(NODES_FILE):
        return jsonify({})

    import requests as req
    with open(NODES_FILE) as f:
        nodes = json.load(f)

    data = {}
    for name, url in nodes.items():
        try:
            res = req.get(f"{url}/api/node/status", timeout=2)
            data[name] = {"status": "online", "containers": res.text.strip().split("\n")}
        except Exception:
            data[name] = {"status": "offline", "containers": []}

    return jsonify(data)

@app.route("/api/node/status")
def node_status():
    """Endpoint for remote nodes to expose their status"""
    status = read_file(f"{STATE}/node-status.txt")
    return "\n".join([l.strip() for l in status])

@app.route("/api/cluster/restart/<node>/<container>", methods=["POST"])
@requires_auth("admin")
def cluster_restart(node, container):
    if not os.path.exists(NODES_FILE):
        return jsonify({"error": "no nodes configured"}), 404

    import requests as req
    with open(NODES_FILE) as f:
        nodes = json.load(f)

    if node not in nodes:
        return jsonify({"error": "node not found"}), 404

    try:
        res = req.post(f"{nodes[node]}/api/restart/{container}", timeout=5)
        return jsonify({"status": "ok", "node": node, "container": container})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
