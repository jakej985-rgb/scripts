# Changelog

## v1.2.0 (2026-04-08)

* **Autonomous Orchestration:**
    * Implemented `scaling.py` for dynamic horizontal scaling with persistent cooldowns.
    * Integrated `reconcile.py` with dependency enforcement (e.g., VPN -> App sequencing).
    * Created dynamic `registry.py` that auto-discovers compose stacks from the `docker/` directory.
* **Distributed Stability:**
    * Implemented `leader.py` for priority-based cluster leadership election.
    * Added `guards.py` to ensure only active masters execute management actions.
    * Hardened `run.sh` supervisor with exponential backoff for crash-loop protection.
* **Observability & DR:**
    * Implemented `health_score.py` aggregator for system stability ranking and TTR metrics.
    * Added `chaos_test.py` resilience agent for automated "destructive" testing.
    * Created `scripts/restore.sh` for one-click disaster recovery from archives.
* **Security & Performance:**
    * Hardened API against shell injection by removing all `shell=True` calls.
    * Optimized metrics history API using high-performance `tail` strategies.
    * Implemented thread-safe, segmented health files to prevent lost-update race conditions.

## v1.1.0 (2026-04-08)

* **Security Hardening:**
    * Scrubbed 6 leaked credentials from full Git history.
    * Replaced plaintext passwords with Bcrypt hashes in `users.json`.
    * Implemented image allowlist validation in container deployment API.
* **Architecture Standardization:**
    * Migrated shell-based agents to standardized Python implementations (`monitor.py`, `anomaly.py`, etc.).
    * Implemented atomic state saves across all agents to prevent file corruption.
    * Added `AUTO-ROOT` detection to all shell scripts for position-independent execution.

## v1.0.0

* Initial public release
* Agent-based system
* Dashboard + RBAC
* Metrics + anomaly detection
* Scaling + cluster support
