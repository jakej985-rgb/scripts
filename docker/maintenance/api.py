from flask import Flask, jsonify, request, abort                   
import subprocess                                                  
                                                                          
app = Flask(__name__)                                                     
                                                                          
API_KEY = "m3tal-secret-key"  # CHANGE THIS                                         
                                                                                    
def auth():                                                                         
    key = request.headers.get("X-API-Key")                                          
    if key != API_KEY:                                                              
        abort(403)                                                                  

def run(cmd):
    return subprocess.getoutput(cmd)

@app.route("/containers")
def containers():
    auth()

    output = run("docker stats --no-stream --format '{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}'")
    result = []

    for line in output.splitlines():
        name, cpu, mem = line.split("|")
        status = run(f"docker inspect -f '{{{{.State.Status}}}}' {name}")
        result.append({
            "name": name,
            "cpu": cpu,
            "mem": mem,
            "status": status
        })

    return jsonify(result)

@app.route("/<action>/<name>")
def action(action, name):
    auth()

    if action not in ["start", "stop", "restart"]:
        return "invalid", 400

    run(f"docker {action} {name}")
    return "ok"

app.run(host="0.0.0.0", port=5000)
