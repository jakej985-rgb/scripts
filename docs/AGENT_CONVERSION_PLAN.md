# Agent Conversion Plan (Bash → Python)

## Goal
Migrate control-plane agents from Bash to Python while maintaining compatibility and stability.

---

## Strategy: Phased Hybrid Migration
- Keep `run.sh` as orchestrator
- Replace agents one-by-one with Python
- Maintain same input/output contracts (JSON files)

---

## Phase 0 – Foundation
### Tasks
- Create `/control-plane/python/` directory
- Add shared utilities:
  - `state.py` (read/write JSON safely)
  - `paths.py` (central path resolution)
  - `logger.py`

### Output
Reusable core modules for all agents

---

## Phase 1 – Metrics Layer (LOW RISK)
### Convert
- monitor.sh → monitor.py
- metrics.sh → metrics.py

### Reason
- No destructive actions
- Easy validation

---

## Phase 2 – Anomaly Detection
### Convert
- anomaly-agent.sh → anomaly.py

### Add
- Rule-based detection system
- Threshold configs

---

## Phase 3 – Decision Engine (CRITICAL)
### Convert
- decision-engine.sh → decision.py

### Improvements
- Structured decision objects
- Priority system
- Deduplication

---

## Phase 4 – Reconcile Layer (KEEP BASH PARTIAL)
### Hybrid
- Python generates actions
- Bash executes system commands

Files:
- decision.py → outputs actions
- reconcile.sh → executes docker/system commands

---

## Phase 5 – Registry + State Manager
### Convert
- registry.sh → registry.py

### Add
- Service tracking
- Health scoring

---

## Execution Flow (Final)
```
run.sh
  ↓
python monitor.py
python metrics.py
python anomaly.py
python decision.py
bash reconcile.sh
python registry.py
```

---

## File Contracts (STRICT)
| File | Producer | Consumer |
|------|---------|---------|
| metrics.json | monitor | metrics |
| normalized_metrics.json | metrics | anomaly |
| anomalies.json | anomaly | decision |
| decisions.json | decision | reconcile |

---

## Python Standards
- Always validate JSON before writing
- Use atomic writes
- Never overwrite blindly

Example:
```python
with open(tmp, 'w') as f:
    json.dump(data, f)
os.replace(tmp, target)
```

---

## Rollback Strategy
- Keep original `.sh` files during migration
- Toggle via run.sh

---

## Risks
- Mixed runtime environment
- Path inconsistencies

Mitigation:
- Central `paths.py`

---

## Future State
- Full Python control-plane service
- Optional API layer
- Event-driven architecture

---

## Summary
This plan minimizes risk while upgrading reliability and scalability.
