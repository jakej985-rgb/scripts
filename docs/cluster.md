# Cluster Operations

M3TAL features zero-configuration multi-node discovery and high-availability leadership.

---

## Leadership Election

Every node running the agent stack participates in a priority-based election managed by `leader.py`.

* **Active Primary**: The node with the highest priority acts as the Master.
* **Standby Followers**: All other nodes stay in Standby mode, ready to take over if the Master heartbeats fail.

---

## Cluster Features

* **Discoverability**: Nodes auto-populate on the dashboard via the registry.
* **Coordination**: The Master node coordinates actions across the cluster.
* **Reconciliation**: Nodes synchronize workloads matching `.yml` definitions in the shared `docker/` directory.
