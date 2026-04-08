# Changelog

## v1.1.0 (2026-04-08)

*   **Security Hardening:**
    *   Scrubbed 6 leaked credentials from full Git history.
    *   Replaced plaintext passwords with Bcrypt hashes in `users.json`.
    *   Implemented image allowlist validation in container deployment API.
    *   Fixed `parse_json` logic to handle NDJSON and prevent file-cursor bugs.
*   **Architecture Standardization:**
    *   Migrated shell-based agents to standardized Python implementations (`monitor.py`, `anomaly.py`, etc.).
    *   Implemented atomic state saves across all agents to prevent file corruption.
    *   Added `AUTO-ROOT` detection to all shell scripts for position-independent execution.
    *   Switched agent container to lightweight `docker:24-cli` image.
*   **Infrastructure:**
    *   Fixed Traefik volume path fragility.
    *   Standardized environment variable usage for VPN and Database credentials.
    *   Improved `install.sh` to preserve `.env.example` configurations.

## v1.0.0

* Initial public release
* Agent-based system
* Dashboard + RBAC
* Metrics + anomaly detection
* Scaling + cluster support
