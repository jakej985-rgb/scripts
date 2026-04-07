# Cluster Operations

M3TAL features zero-configuration multi-node discovery.

Every node running the agent stack fires a 10s heartbeat via `node-agent.sh` to the Control Plane `MASTER_URL`.

Features:
- **Discoverability**: Nodes auto-populate on the dashboard.
- **Scheduling**: The Master routes new containers via `scheduler.sh`.
- **Reconciliation**: Nodes synchronize workloads matching `.yml` definitions.
