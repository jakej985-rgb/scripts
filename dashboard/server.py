from flask import Flask, render_template, jsonify, request, redirect, Response, abort
from flask_socketio import SocketIO
from functools import wraps
import subprocess
import csv
import json
import os
import time
import threading
import re
from auth import get_role

# Image prefixes allowlist for deployment
ALLOWED_IMAGES_PREFIXES = [
    "lscr.io/linuxserver/",
    "ghcr.io/",
    "containrrr/",
    "amir20/",
    "portainer/",
    "node:",
    "postgres:",
    "traefik:",
    "python:",
    "ubuntu:"
]

def validate_image(image: str) -> bool:
    if not image: return False
    return any(image.startswith(p) for p in ALLOWED_IMAGES_PREFIXES)

def get_known_containers():
    try:
        out = subprocess.check_output(
            ["docker", "ps", "-a", "--format", "{{.Names}}"], text=True
        )
        return set(out.strip().split("\n"))
    except:
        return set()

def validate_container(name):
    if not name: abort(400, "container name required")
    allowed = re.compile(r'^[a-zA-Z0-9_\-\.]+$')
    if not allowed.match(name):
        abort(400, "invalid container name format")
    if name not in get_known_containers():
        abort(404, "container not found")

app = Flask(__name__)
socketio = SocketIO(app)

STATE = "control-plane/state"
LOGS = "control-plane/state/logs"
USERS_FILE = "/docker/dashboard/users.json"
NODES_FILE = "control-plane/config/nodes.json"
JOBS_FILE = "control-plane/config/jobs.json"

# ── v5.1: In-Memory Node Registry (heartbeat-based) ──

DISCOVERED_NODES = {}
NODES_LOCK = threading.Lock()

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

def get_active_nodes():
    """Return discovered nodes + static nodes, pruning stale heartbeats (>30s)"""
    now = time.time()
    nodes = {}

    # Static nodes from nodes.json (fallback)
    if os.path.exists(NODES_FILE):
        with open(NODES_FILE) as f:
            static = json.load(f)
        for name, url in static.items():
            nodes[name] = {"url": url, "source": "static"}

    # Discovered nodes via heartbeat (override static if same name)
    with NODES_LOCK:
        for name, data in DISCOVERED_NODES.items():
            if now - data["last_seen"] < 30:
                port = data.get("port", "8080")
                nodes[name] = {
                    "url": f"http://{data['ip']}:{port}",
                    "ip": data["ip"],
                    "last_seen": data["last_seen"],
                    "source": "heartbeat"
                }

    return nodes

def get_cpu_usage():
    """Get system CPU usage percentage"""
    try:
        out = subprocess.check_output(
            ["grep", "cpu ", "/proc/stat"], text=True
        ).strip().split()
        idle = float(out[4])
        total = sum(float(x) for x in out[1:])
        return round(100 * (1 - idle / total), 1)
    except Exception:
        return 0.0

def get_mem_usage():
    """Get system memory usage percentage"""
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        mem = {}
        for line in lines[:5]:
            parts = line.split()
            mem[parts[0].rstrip(":")] = int(parts[1])
        total = mem.get("MemTotal", 1)
        avail = mem.get("MemAvailable", total)
        return round(100 * (1 - avail / total), 1)
    except Exception:
        return 0.0

# ── v4.2/v7.1: Token Auth ──

def requires_auth(role_required=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Support header auth Or querystring for browser convenience
            token = request.headers.get("Authorization")
            if not token:
                token = request.args.get("token")
                
            role = get_role(token)
            if not role:
                return Response("Token required", 401)

            if role_required:
                role_hierarchy = {"admin": 3, "operator": 2, "viewer": 1}
                if role_hierarchy.get(role, 0) < role_hierarchy.get(role_required, 0):
                    return abort(403)
                    
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ══════════════════════════════════════
# ROUTES: Dashboard
# ══════════════════════════════════════

@app.route("/")
def index():
    version = "1.0.0"
    if os.path.exists("VERSION"):
        with open("VERSION") as f:
            version = f.read().strip()
    return render_template("index.html", version=version)

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

# ══════════════════════════════════════
# ROUTES: JSON API (state)
# ══════════════════════════════════════

@app.route("/api/state")
@requires_auth("viewer")
def api_state():
    containers = [] # managed via json now
    analysis = read_file(f"{STATE}/analysis.txt")
    actions = [] # decisions.json now
    disk = read_file(f"{STATE}/disk.txt")
    logs = read_file(f"{LOGS}/actions.log")[-50:]
    retries = read_retries()
    cooldowns = read_cooldowns()
    ai_recs = read_file(f"{STATE}/ai-recommendations.txt")
    anomalies = [] # JSON handled below
    deps = read_file(f"{STATE}/dependency-issues.txt")
    metrics = read_file(f"{STATE}/metrics.txt")
    scaling_log = read_file(f"{LOGS}/scaling.log")[-20:]
    reconcile_log = read_file(f"{LOGS}/reconcile.log")[-20:]
    scheduler_log = read_file(f"{LOGS}/scheduler.log")[-20:]

    # Read json states fallback gracefully
    def parse_json(path):
        try:
            with open(path) as f:
                return [json.loads(line) if line.startswith('{') else json.loads(f.read()) for line in f if line.strip()]
        except Exception:
            return []

    return jsonify({
        "containers": parse_json(f"{STATE}/state.json"),
        "analysis": [l.strip() for l in analysis],
        "decisions": parse_json(f"{STATE}/decisions.json"),
        "disk": [l.strip() for l in disk],
        "logs": [l.strip() for l in logs],
        "retries": retries,
        "cooldowns": cooldowns,
        "ai_recs": [l.strip() for l in ai_recs],
        "anomalies": parse_json(f"{STATE}/anomalies.json"),
        "deps": [l.strip() for l in deps],
        "metrics": [l.strip() for l in metrics],
        "scaling_log": [l.strip() for l in scaling_log],
        "reconcile_log": [l.strip() for l in reconcile_log],
        "scheduler_log": [l.strip() for l in scheduler_log],
        "timestamp": int(time.time()),
    })

# ══════════════════════════════════════
# ROUTES: v4 Container Control
# ══════════════════════════════════════

@app.route("/api/restart/<name>", methods=["POST"])
@requires_auth("operator")
def restart(name):
    validate_container(name)
    subprocess.run(["docker", "restart", name])
    token = request.headers.get("Authorization", "unknown")
    with open(f"{LOGS}/actions.log", "a") as f:
        f.write(f"{time.strftime('%c')} RESTART {name} by token={token[:8]}...\n")
    return jsonify({"status": "ok", "action": "restart", "container": name})

@app.route("/api/stop/<name>", methods=["POST"])
@requires_auth("operator")
def stop(name):
    validate_container(name)
    subprocess.run(["docker", "stop", name])
    token = request.headers.get("Authorization", "unknown")
    with open(f"{LOGS}/actions.log", "a") as f:
        f.write(f"{time.strftime('%c')} STOP {name} by token={token[:8]}...\n")
    return jsonify({"status": "ok", "action": "stop", "container": name})

@app.route("/api/start/<name>", methods=["POST"])
@requires_auth("operator")
def start(name):
    validate_container(name)
    subprocess.run(["docker", "start", name])
    token = request.headers.get("Authorization", "unknown")
    with open(f"{LOGS}/actions.log", "a") as f:
        f.write(f"{time.strftime('%c')} START {name} by token={token[:8]}...\n")
    return jsonify({"status": "ok", "action": "start", "container": name})

@app.route("/api/approve", methods=["POST"])
@requires_auth("admin")
def approve():
    subprocess.run(["control-plane/agents/action-agent.sh", "force"])
    token = request.headers.get("Authorization", "unknown")
    with open(f"{LOGS}/actions.log", "a") as f:
        f.write(f"{time.strftime('%c')} APPROVE by token={token[:8]}...\n")
    return jsonify({"status": "ok", "action": "approve"})

# ══════════════════════════════════════
# ROUTES: v4.1 Metrics Time-Series
# ══════════════════════════════════════

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

# ══════════════════════════════════════
# ROUTES: v5.1 Service Discovery
# ══════════════════════════════════════

@app.route("/api/register", methods=["POST"])
def register_node():
    name = request.form.get("name", "")
    ip = request.form.get("ip", "")
    port = request.form.get("port", "8080")

    if not name or not ip:
        return "missing fields", 400

    with NODES_LOCK:
        DISCOVERED_NODES[name] = {
            "ip": ip,
            "port": port,
            "last_seen": time.time()
        }

    return "ok"

@app.route("/api/nodes")
@requires_auth("viewer")
def list_nodes():
    nodes = get_active_nodes()
    return jsonify({
        name: {
            "url": data["url"],
            "source": data["source"],
            "last_seen": data.get("last_seen"),
        }
        for name, data in nodes.items()
    })

# ══════════════════════════════════════
# ROUTES: v5 Cluster
# ══════════════════════════════════════

@app.route("/api/cluster")
@requires_auth("viewer")
def cluster_status():
    import requests as req
    nodes = get_active_nodes()

    data = {}
    for name, info in nodes.items():
        url = info["url"]
        try:
            res = req.get(f"{url}/api/node/status", timeout=2)
            data[name] = {
                "status": "online",
                "containers": [c for c in res.text.strip().split("\n") if c],
                "source": info["source"]
            }
        except Exception:
            data[name] = {"status": "offline", "containers": [], "source": info["source"]}

    return jsonify(data)

@app.route("/api/node/status")
def node_status():
    """Endpoint for remote nodes to expose their status"""
    status = read_file(f"{STATE}/node-status.txt")
    return "\n".join([l.strip() for l in status])

@app.route("/api/node/metrics")
def node_metrics():
    """v6: Expose local node metrics for placement decisions"""
    running = subprocess.check_output(
        ["docker", "ps", "-q"], text=True
    ).strip().split("\n")
    container_count = len([c for c in running if c])

    return jsonify({
        "cpu": get_cpu_usage(),
        "mem": get_mem_usage(),
        "containers": container_count
    })

@app.route("/api/cluster/restart/<node>/<container>", methods=["POST"])
@requires_auth("admin")
def cluster_restart(node, container):
    import requests as req
    nodes = get_active_nodes()

    if node not in nodes:
        return jsonify({"error": "node not found"}), 404

    try:
        res = req.post(f"{nodes[node]['url']}/api/restart/{container}", timeout=5)
        return jsonify({"status": "ok", "node": node, "container": container})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ══════════════════════════════════════
# ROUTES: v5.2 Job Scheduler (Cluster)
# ══════════════════════════════════════

@app.route("/api/run_job/<job>", methods=["POST"])
@requires_auth("operator")
def run_job_cluster(job):
    """Dispatch a job to all active nodes"""
    import requests as req
    nodes = get_active_nodes()
    results = {}

    for name, info in nodes.items():
        try:
            res = req.post(f"{info['url']}/api/execute/{job}", timeout=10)
            results[name] = "ok"
        except Exception as e:
            results[name] = f"error: {str(e)}"

    return jsonify({"job": job, "results": results})

@app.route("/api/execute/<job>", methods=["POST"])
@requires_auth("operator")
def execute_job(job):
    """Execute a job locally on this node"""
    if not os.path.exists(JOBS_FILE):
        return jsonify({"error": "no jobs configured"}), 404

    with open(JOBS_FILE) as f:
        jobs = json.load(f)

    for j in jobs:
        if j["name"] == job:
            subprocess.Popen(j["command"], shell=True)
            with open(f"{LOGS}/scheduler.log", "a") as lf:
                lf.write(f"{time.strftime('%c')} API: executed job '{job}'\n")
            return jsonify({"status": "ok", "job": job})

    return jsonify({"error": "job not found"}), 404

# ══════════════════════════════════════
# ROUTES: v6 Container Placement
# ══════════════════════════════════════

@app.route("/api/deploy", methods=["POST"])
@requires_auth("admin")
def deploy_container():
    """Deploy container to best available node based on load"""
    import requests as req
    image = request.form.get("image", "")
    prefer_node = request.form.get("node", "auto")

    if not image:
        return jsonify({"error": "image required"}), 400

    if prefer_node != "auto":
        # Deploy to specific node
        nodes = get_active_nodes()
        if prefer_node in nodes:
            target_url = nodes[prefer_node]["url"]
        else:
            return jsonify({"error": f"node '{prefer_node}' not found"}), 404
    else:
        # Auto-placement: choose least loaded node
        target_url = choose_best_node()
        if not target_url:
            # Fallback to local
            target_url = "http://localhost:8080"

    try:
        res = req.post(f"{target_url}/api/run_container",
                      data={"image": image}, timeout=10)
        return jsonify({"status": "ok", "image": image, "node": target_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def choose_best_node():
    """v6: Score nodes by load and pick the least loaded"""
    import requests as req
    nodes = get_active_nodes()
    best_url = None
    best_score = 9999

    for name, info in nodes.items():
        try:
            res = req.get(f"{info['url']}/api/node/metrics", timeout=2).json()
            score = res["cpu"] + res["mem"] + (res["containers"] * 5)
            if score < best_score:
                best_score = score
                best_url = info["url"]
        except Exception:
            continue

    return best_url

@app.route("/api/run_container", methods=["POST"])
@requires_auth("operator")
def run_container():
    """Start a container on this node"""
    image = request.form.get("image", "")
    name = request.form.get("name", "")

    if not image:
        return jsonify({"error": "image required"}), 400

    if not validate_image(image):
        return jsonify({"error": "image not in allowlist"}), 403

    cmd = ["docker", "run", "-d", "--restart", "unless-stopped"]
    if name:
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', name):
             return jsonify({"error": "invalid container name"}), 400
        cmd += ["--name", name]
    cmd.append(image)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        token = request.headers.get("Authorization", "unknown")
        with open(f"{LOGS}/actions.log", "a") as f:
            f.write(f"{time.strftime('%c')} DEPLOY {image} as {name} by token={token[:8]}...\n")
        return jsonify({"status": "ok", "container_id": result.stdout.strip()[:12]})
    else:
        return jsonify({"error": result.stderr.strip()}), 500

# ══════════════════════════════════════
# ROUTES: v6.2 Rolling Updates
# ══════════════════════════════════════

@app.route("/api/rolling_update/<name>", methods=["POST"])
@requires_auth("admin")
def rolling_update(name):
    """Zero-downtime update: start new → verify → remove old → rename"""
    new_name = f"{name}-update"

    # Get current image
    try:
        image = subprocess.check_output(
            ["docker", "inspect", "--format", "{{.Config.Image}}", name],
            text=True
        ).strip()
    except subprocess.CalledProcessError:
        return jsonify({"error": f"container '{name}' not found"}), 404

    # Pull latest
    subprocess.run(["docker", "pull", image], capture_output=True)

    # Start new container with same image (latest)
    result = subprocess.run(
        ["docker", "run", "-d", "--name", new_name, "--restart", "unless-stopped", image],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return jsonify({"error": f"failed to start new: {result.stderr.strip()}"}), 500

    # Wait for new container to be running
    time.sleep(5)
    status = subprocess.check_output(
        ["docker", "inspect", "--format", "{{.State.Status}}", new_name],
        text=True
    ).strip()

    if status != "running":
        subprocess.run(["docker", "rm", "-f", new_name])
        return jsonify({"error": "new container failed to start, rolled back"}), 500

    # Stop old, remove old, rename new
    subprocess.run(["docker", "stop", name])
    subprocess.run(["docker", "rm", name])
    subprocess.run(["docker", "rename", new_name, name])

    with open(f"{LOGS}/actions.log", "a") as f:
        f.write(f"{time.strftime('%c')} Rolling update: {name} ({image})\n")

    return jsonify({"status": "ok", "container": name, "image": image})

@app.route("/update/<name>")
@requires_auth("operator")
def update(name):
    """Simple GET route to pull and restart container (for easy webhook/browser usage)"""
    try:
        image = subprocess.check_output(["docker", "inspect", "--format", "{{.Config.Image}}", name], text=True).strip()
        subprocess.run(["docker", "pull", image])
    except:
        pass
    subprocess.run(["docker", "restart", name])
    with open(f"{LOGS}/actions.log", "a") as f:
        f.write(f"{time.strftime('%c')} Dashboard: Simple updated {name}\n")
    return redirect("/")

# ══════════════════════════════════════
# WEBSOCKET METRICS STREAM
# ══════════════════════════════════════

def stream_metrics():
    while True:
        try:
            if os.path.exists(f"{STATE}/metrics.txt"):
                with open(f"{STATE}/metrics.txt", "r") as f:
                    data = f.read()
                socketio.emit("metrics", {"data": data})
        except Exception:
            pass
        time.sleep(2)

threading.Thread(target=stream_metrics, daemon=True).start()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8080, allow_unsafe_werkzeug=True)
