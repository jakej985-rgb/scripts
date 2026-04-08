# 🤖 M3TAL Agents Documentation

M3TAL uses a decentralized pipeline of Python agents to maintain the health and state of your media server.

---

## 🏗️ The Agent Loop
The system follows a continuous **Sense → Think → Act** loop. Every agent is independent and communicates only via standardized JSON files in `control-plane/state/`.

### 1. Sensing (The Eyes)
*   **Registry (`registry.py`)**: The discovery engine. It scans your `docker/` folder and identifies which containers M3TAL is responsible for.
*   **Monitor (`monitor.py`)**: Checks the real-time status of Docker containers. It notes if a container is "Up", "Exited", or "Missing".
*   **Metrics (`metrics.py`)**: Gathers performance data (CPU, RAM, I/O). It also maintains a historical CSV for the dashboard charts.
*   **Observer (`observer.py`)**: Watches the system logs for critical errors or crashes across node boundaries.

### 2. Thinking (The Brain)
*   **Anomaly (`anomaly.py`)**: Analyzes the health and metrics data. It classifies problems as "Recoverable" (stopped container), "Critical" (memory leak), or "Transient" (momentary load spike).
*   **Scaling (`scaling.py`)**: Decides if we need more or fewer copies of a service based on user-defined CPU thresholds.
*   **Decision (`decision.py`)**: The final planner. It looks at the anomalies and scaling requests and decides on a concrete action (Restart, Start, Scale). It enforces **cooldowns** to prevent loops.

### 3. Acting (The Hands)
*   **Reconcile (`reconcile.py`)**: The enforcer. It executes the planned actions using Docker commands. It also ensures that all containers have the correct storage mounts and that dependencies (like VPNs) are running.
*   **Leader (`leader.py`)**: Manages cluster leadership. It ensures that only one "Active" node is issuing commands, while others stay in "Standby" (Follower) mode.

---

## 🛡️ Stability Features
*   **Idempotency**: Agents can be run 100 times in a row and will only take action if the system state doesn't match the desired state.
*   **Atomic State**: No agent writes directly to a file while another is reading. We use a "write-to-tmp-then-rename" pattern to prevent file corruption.
*   **Crash Protection**: If an agent crashes, the **Supervisor (`run.sh`)** will restart it automatically with an exponential backoff to avoid CPU saturation.

---

## 🛠️ Management
You can see the status of all agents in the **Dashboard** under the "Agents" or "Health" section. Each agent logs its thoughts to `control-plane/state/logs/<agent_name>.log`.
