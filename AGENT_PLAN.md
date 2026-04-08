# 🤖 M3TAL Media Server — Production Agent Plan (v1.2.0)

## 🎯 Objective

Transform the M3TAL Media Server from a fragile container stack into a **Fully Autonomous, Self-Healing Cloud-Native Orchestration Plane**.

The system now operates on a distributed state-machine model where intelligence is decoupled from enforcement, and reliability is ensured via atomic JSON contracts.

---

## 🏛️ CORE ARCHITECTURE

### 🌏 Distributed Leadership

* **Agent**: `leader.py`
* **Logic**: Uses a priority-based election model (defined in `cluster.yml`) and unique node identity (Host+IP) to ensure only one node acts as the **Active Primary**.
* **Enforcement**: All agents use `utils/guards.py` to check `leader.txt` before execution.

### 💾 Atomic State Management

* **Path**: `control-plane/state/`
* **Access**: All agents use `utils/state.py` for atomic "write-then-rename" operations to prevent JSON corruption during crashes.
* **Isolation**: No agent shares an output file (Single Writer Pattern).

### 👮 Standardized Supervisor

* **Agent**: `run.sh`
* **Logic**: Continuous background supervisor with **exponential backoff** crash protection.
* **Reliability**: Signals and exit codes (0/1) are used to distinguish between healthy Standby (Follower) and actual process failure.

---

## ⚙️ IMPLEMENTATION STATUS

### ✅ PHASE 1 — FOUNDATION (COMPLETE)

* **[COMPLETED]** `init.sh`: Self-healing state scaffolding and default user provisioning (`admin/admin123`).
* **[COMPLETED]** `utils/paths.py`: Absolute path determinism (AUTO-ROOT pattern).
* **[COMPLETED]** `utils/logger.py`: Standardized logging with 10MB/3-file rotation.

### ✅ PHASE 2 — PERCEPTION & INTELLIGENCE (COMPLETE)

* **[COMPLETED]** `registry.py`: Dynamic discovery. Scans `docker/` for compose files; no manual container lists.
* **[COMPLETED]** `monitor.py`: High-frequency health polling into segmented state files.
* **[COMPLETED]** `metrics.py`: Deep telemetry (CPU, Mem, Net I/O, Block I/O) for system and containers.

### ✅ PHASE 3 — COGNITION & DECISION (COMPLETE)

* **[COMPLETED]** `anomaly.py`: Classification logic using deep metrics and health feedback.
* **[COMPLETED]** `scaling.py`: Autonomous horizontal scaling based on CPU thresholds with persistent 5m cooldowns.
* **[COMPLETED]** `decision.py`: Action planning with stateful cooldowns to prevent "flapping" or restart storms.

### ✅ PHASE 4 — ENFORCEMENT & HARDENING (COMPLETE)

* **[COMPLETED]** `reconcile.py`: Enforcer agent for `start/stop/restart/scale` actions + Dependency Enforcement.
* **[COMPLETED]** `health_score.py`: Consolidated aggregator that calculates stability scores and TTR (Time-To-Recovery).
* **[COMPLETED]** `chaos_test.py`: Destructive resilience tester that logs events for TTR analysis.

---

## 🛡️ SECURITY & RELIABILITY LOCKS

| Feature | Protection |
| :--- | :--- |
| **Credential Scrub** | 100% of historical leaked passwords removed via destructive rewrite. |
| **Auth** | Dashboard uses BCrypt token-based authentication (Role: admin, operator, viewer). |
| **Shell Hardening** | Removed `shell=True` and implemented strict `ALLOWED_IMAGES` allowlisting. |
| **Disk Safety** | Automatic log rotation and idempotent `backup.sh` with retention logic. |
| **Path Safety** | No hardcoded paths; all components resolve relative to git toplevel. |

---

## 🔮 FUTURE ROADMAP (PHASE 11+)

### 📡 Phase 11: Global Distributed Registry

* **Implement Gossip protocol** (e.g., Memberlist) for agents to share `registry.json` across nodes without a central DB.
* **Broadcast node heartbeats** to the Dashboard in real-time.

### 🧠 Phase 12: Predictable Scaling (AI Feedback)

* **Integrate simple linear regression** to predict scaling needs *before* the threshold is hit (Predictive Scaling).
* **Implement "Global Load Balancing"** — if one node is saturated, `decision.py` moves workload metadata to another.

### 🎨 Phase 13: Dashboard Evolution

* **Move from Flask/HTML** to a React/Next.js "Admin Center" with real-time WebSocket metrics visualization.
* **Add a "Chaos Center" UI** to trigger specific file corruptions for live resilience training.

---

## 🏁 DEFINITION OF DONE

The system is considered healthy if:

1. **Registry** reflects all active Docker volumes and containers.
2. **Leader** is established and visible in `leader.txt`.
3. **Health Score** is > 85% with no persistent "Stalled" agents.
4. **TTR** for container restarts is < 15 seconds.
5. **Scaling** occurs within 60s of sustained high load.
