from flask import Flask, render_template, jsonify
import os
import time

app = Flask(__name__)

STATE = "/docker/state"
LOGS = "/docker/logs"

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
            path = os.path.join(cd_dir, name)
            try:
                with open(path) as f:
                    ts = int(f.read().strip())
                    cooldowns[name] = int(time.time()) - ts
            except (ValueError, IOError):
                cooldowns[name] = -1
    return cooldowns

@app.route("/")
def index():
    containers = read_file(f"{STATE}/containers.txt")
    analysis = read_file(f"{STATE}/analysis.txt")
    actions = read_file(f"{STATE}/actions.txt")
    disk = read_file(f"{STATE}/disk.txt")
    logs = read_file(f"{LOGS}/actions.log")[-50:]
    retries = read_retries()
    cooldowns = read_cooldowns()
    ai_recs = read_file(f"{STATE}/ai-recommendations.txt")

    return render_template("index.html",
        containers=containers,
        analysis=analysis,
        actions=actions,
        disk=disk,
        logs=logs,
        retries=retries,
        cooldowns=cooldowns,
        ai_recs=ai_recs,
    )

@app.route("/api/state")
def api_state():
    containers = read_file(f"{STATE}/containers.txt")
    analysis = read_file(f"{STATE}/analysis.txt")
    actions = read_file(f"{STATE}/actions.txt")
    disk = read_file(f"{STATE}/disk.txt")
    logs = read_file(f"{LOGS}/actions.log")[-50:]
    retries = read_retries()
    cooldowns = read_cooldowns()
    ai_recs = read_file(f"{STATE}/ai-recommendations.txt")

    return jsonify({
        "containers": [l.strip() for l in containers],
        "analysis": [l.strip() for l in analysis],
        "actions": [l.strip() for l in actions],
        "disk": [l.strip() for l in disk],
        "logs": [l.strip() for l in logs],
        "retries": retries,
        "cooldowns": cooldowns,
        "ai_recs": [l.strip() for l in ai_recs],
        "timestamp": int(time.time()),
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
