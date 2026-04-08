# 🤖 M3tal Media Server – AI Execution Plan

## 🎯 Objective

Convert system from:

* Script-based execution

Into:

* Stateful, self-healing control plane
* Deterministic agent system
* Autonomous Docker recovery engine

---

# 🧠 GLOBAL RULES (MANDATORY)

1. **All agents must be idempotent**
2. **No agent creates missing state files**
3. **All state lives in:**

   ```
   control-plane/state/
   ```
4. **All containers must use `/mnt`**
5. **All actions must be logged**
6. **Prefer simple + reliable over complex**

---

# 📦 REQUIRED STATE STRUCTURE

```
control-plane/state/
  leader.txt
  health.json
  metrics.json
  decisions.json
  registry.json
```

---

# ⚙️ PHASE 1 — CORE STABILITY (DO FIRST)

## ✅ Task 1: Build init.sh (State Bootstrap)

### Requirements

* Create:

  * `control-plane/state/`
  * `logs/`
* Ensure files exist:

  * leader.txt
  * health.json
  * metrics.json
  * decisions.json
  * registry.json
* Set permissions:

  ```bash
  sudo chown -R 1000:1000 .
  ```

### Success Criteria

* No script fails due to missing files

---

## ✅ Task 2: Replace run.sh with Supervisor

### Requirements

* Must:

  * Launch all agents
  * Restart on crash
  * Log output per agent
  * Never exit

### Implementation

```bash
#!/bin/bash

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$BASE_DIR/logs"
mkdir -p "$LOG_DIR"

run_agent() {
  local name=$1
  local script=$2

  while true; do
    echo "[RUN] $name"
    bash "$script" >> "$LOG_DIR/$name.log" 2>&1

    echo "[CRASH] $name restarting in 5s"
    sleep 5
  done
}

run_agent monitor "$BASE_DIR/control-plane/agents/monitor.sh" &
run_agent metrics "$BASE_DIR/control-plane/agents/metrics.sh" &
run_agent anomaly "$BASE_DIR/control-plane/agents/anomaly-agent.sh" &
run_agent decision "$BASE_DIR/control-plane/agents/decision-engine.sh" &
run_agent reconcile "$BASE_DIR/control-plane/agents/reconcile.sh" &
run_agent registry "$BASE_DIR/control-plane/agents/registry.sh" &

wait
```

### Success Criteria

* Killing any agent → it restarts automatically

---

## ✅ Task 3: Enforce Data Contracts

Each agent MUST:

| Agent     | Writes                   | Reads                |
| --------- | ------------------------ | -------------------- |
| monitor   | health.json              | docker               |
| metrics   | metrics.json             | system               |
| anomaly   | decisions.json (issues)  | health + metrics     |
| decision  | decisions.json (actions) | decisions            |
| reconcile | none                     | decisions + registry |
| registry  | registry.json            | static config        |

### Rule

👉 One file per agent (no overlap)

---

# ⚙️ PHASE 2 — INTELLIGENCE LAYER

## ✅ Task 4: Build Anomaly Classification

### Input

* health.json
* metrics.json

### Output (decisions.json)

```json
{
  "issues": [
    {
      "type": "recoverable",
      "target": "qbittorrent",
      "reason": "container stopped"
    }
  ]
}
```

### Required Types

* transient
* recoverable
* critical
* misconfig

---

## ✅ Task 5: Decision Engine

### Input

* issues

### Output

```json
{
  "actions": [
    {
      "type": "restart",
      "target": "qbittorrent"
    }
  ]
}
```

### Add MUST-HAVE

* cooldown system:

  * prevent restart loops
  * track last action timestamps

---

# ⚙️ PHASE 3 — SELF-HEALING

## ✅ Task 6: Reconcile Agent (Enforcer)

### Responsibilities

* Enforce actual system state

### Required Actions

```bash
docker restart <container>
docker start <container>
docker stop <container>
```

### Rules

* Idempotent
* Logged
* Safe retries

---

## ✅ Task 7: Registry Agent

### Output

```json
{
  "containers": [
    "qbittorrent",
    "radarr",
    "sonarr",
    "tdarr"
  ],
  "paths": {
    "root": "/mnt",
    "downloads": "/mnt/downloads",
    "media": "/mnt/media"
  }
}
```

### Purpose

👉 Single source of truth

---

# 💾 STORAGE ENFORCEMENT (CRITICAL)

ALL containers must use:

```yaml
volumes:
  - /mnt:/mnt
```

### Required Paths

| Service     | Path           |
| ----------- | -------------- |
| qBittorrent | /mnt/downloads |
| Radarr      | /mnt/media     |
| Sonarr      | /mnt/media     |

### Success Criteria

* Moves are instant (no copy)
* No duplicate files in downloads

---

# 🔁 EXECUTION LOOP

```
init → supervisor
   ↓
monitor → health.json
metrics → metrics.json
anomaly → issues
decision → actions
reconcile → fix system
   ↺ loop forever
```

---

# ⚠️ GUARDRAILS

* ❌ No hardcoded paths outside `/mnt`
* ❌ No silent failures
* ❌ No agent-to-agent direct calls
* ✅ Everything via state files
* ✅ Everything logged

---

# 🚀 PHASE 4 — ADVANCED (OPTIONAL)

## Add:

* event log (`events.log`)
* restart cooldown tracking
* container dependency graph
* alert system (Discord/webhook)

---

# ✅ DEFINITION OF DONE

System must:

* Detect stopped container
* Classify issue correctly
* Decide proper action
* Restart container automatically
* Avoid restart loops
* Maintain filesystem consistency
