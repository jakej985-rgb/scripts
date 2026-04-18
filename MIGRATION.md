# Migration Guide: v1.1 → v1.3 (Modern)

This guide covers the transition from legacy shell scripts to the **v1.3.0 Autonomous Agent Pipeline** managed by the `m3tal.py` CLI.

---

## 🏗️ What changed

*   **Unified CLI**: All operations are now centralized under `m3tal.py`. No more managing individual shell scripts.
*   **Tiered Orchestration**: Agents are organized into Tiers (Infrastructure, Logic, Polish) ensuring a deterministic startup sequence.
*   **Python-First**: The `install.sh` and `shutdown.sh` scripts are deprecated (and removed) in favor of internal Python logic.
*   **Security Hardening**: Traefik dashboard is now secured by Basic Auth, and agents run with hardened security options.

---

## 🚀 Migration Steps

### 1. Repository Alignment

M3TAL now uses **AUTO-ROOT** detection. Ensure you are running commands from the repository root.

### 2. Dependency Update

The modern pipeline requires `bcrypt` for Traefik security and `Flask-SocketIO` for the dashboard.

```bash
python3 -m pip install -r requirements.txt
```

### 3. Cleanup Legacy Scripts

If you still have `install.sh` or `shutdown.sh` in your root, delete them. They are no longer supported.

### 4. Initialize Infrastructure

Use the new CLI to scaffold the environment and verify repository integrity:

```bash
python3 m3tal.py init
```

### 5. Launch the Control Plane

Start the autonomous supervisor:

```bash
python3 m3tal.py run
```

---

## 🧱 Component Mapping

| Legacy Component | Modern Command | Modern Agent |
| :--- | :--- | :--- |
| `install.sh` | `python3 install.py` | `install.py` |
| `init.sh` | `m3tal init` | `init.py` |
| `run.sh` | `m3tal run` | `run.py` |
| `shutdown.sh` | `m3tal shutdown` | `shutdown.py` |
| `auto-heal.sh` | `m3tal reconcile` | `reconcile.py` |

---

## ⚠️ Important Note

**Configuration Volumes**: Ensure your `.env` is updated using `python3 scripts/config/configure_env.py` to support the new Traefik authentication requirements introduced in v1.3.0.

