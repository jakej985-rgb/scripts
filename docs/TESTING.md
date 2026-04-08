# 🧪 Resilience & Chaos Testing

M3TAL includes a built-in "Chaos Agent" to verify that the self-healing systems are working correctly.

---

## 💥 The Chaos Agent (`chaos_test.py`)
The Chaos Agent is a destructive testing tool. It randomly injects failures into the control plane to see how fast the system can recover.

### What it does:
*   **Deletes** critical state files (like `decisions.json`).
*   **Corrupts** JSON files with garbage data.
*   **Empties** status files.

### How to use it:
By default, the Chaos Agent is disabled for stability. To run a "Chaos Experiment":
1. Open `control-plane/run.sh`.
2. Uncomment the line: `# run_agent chaos "$BASE_DIR/agents/chaos_test.py" python &`.
3. Restart the control plane: `bash control-plane/run.sh`.

---

## 📊 Measuring Performance (TTR)
Once chaos is injected, the system tracks its **Time-To-Recovery (TTR)**.

1. **Check the Stats**: Look in `control-plane/state/chaos_events.json`.
2. **Understand the Metrics**:
   *   `action`: What damage was done (e.g., "delete").
   *   `ttr`: How many seconds it took for the `init.sh` or the agents to repair the file.
   *   `avg_ttr`: The average recovery time for the whole experiment session.

**Goal**: A healthy M3TAL system should have an `avg_ttr` of **less than 15 seconds**.

---

## 🛠️ Manual Testing
If you don't want to use the Chaos Agent, you can test self-healing manually:

### 1. The Container Crash Test
*   Stop a container manually: `docker stop qbittorrent`.
*   Watch `control-plane/state/logs/monitor.log` → It will detect the "offline" state.
*   Watch `control-plane/state/logs/reconcile.log` → Within 60 seconds, it should issue a `docker start` command.

### 2. The File Corruption Test
*   Open `control-plane/state/metrics.json` and delete everything inside it.
*   Wait 5 seconds.
*   The `metrics.py` agent will detect the invalid file and regenerate it automatically.

---

## ⚠️ Safety Warning
**DO NOT RUN THE CHAOS AGENT IN PRODUCTION.** 
It is designed to break things. While M3TAL is designed to fix itself, running chaos experiments while you are trying to watch a movie may result in service interruptions.
