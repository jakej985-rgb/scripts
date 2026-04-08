# M3tal Media Server – Agent System Plan

## Overview
This document defines the architecture, responsibilities, and data flow of the control-plane agent system.

---

## Core Principles
- Single source of truth: `/control-plane/state`
- Deterministic execution order
- Agents are stateless (state lives in files)
- Idempotent operations
- Fail-safe defaults

---

## Directory Structure
```
control-plane/
  agents/
  state/
  logs/
  config/
```

---

## State Files
| File | Owner | Purpose |
|------|------|--------|
| anomalies.json | anomaly-agent | Detected issues |
| decisions.json | decision-engine | Actions to take |
| leader.txt | system | Cluster leader |

---

## Agents

### 1. monitor.sh
Collects raw system + container data

Outputs:
- metrics.json

---

### 2. metrics.sh
Normalizes and aggregates metrics

Inputs:
- metrics.json

Outputs:
- normalized_metrics.json

---

### 3. anomaly-agent.sh
Detects abnormal conditions

Inputs:
- normalized_metrics.json

Outputs:
- anomalies.json

---

### 4. decision-engine.sh
Determines corrective actions

Inputs:
- anomalies.json

Outputs:
- decisions.json

---

### 5. reconcile.sh
Executes actions

Inputs:
- decisions.json

Actions:
- restart container
- scale service
- notify

---

### 6. registry.sh
Tracks system state + services

---

## Execution Flow
```
monitor → metrics → anomaly → decision → reconcile
```

---

## Run Order (STRICT)
1. init.sh
2. monitor.sh
3. metrics.sh
4. anomaly-agent.sh
5. decision-engine.sh
6. reconcile.sh
7. registry.sh

---

## Logging
All agents must log to:
```
control-plane/logs/<agent>.log
```

---

## Future Improvements
- Replace bash agents with Python services
- Add message queue (Redis/NATS)
- Add API layer for control-plane
- Add health scoring system

---

## Failure Handling
- Missing state file → recreate
- Invalid JSON → reset to default
- Agent crash → log + continue

---

## Notes
This system is designed to evolve into a distributed control plane.
