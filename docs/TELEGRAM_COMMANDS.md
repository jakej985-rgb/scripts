# 🤖 M3TAL Telegram Bot — Command Reference (v5.0)

Complete reference for all **24 commands** available via the M3TAL Telegram bot.
Supports both **typed commands** and a fully **button-driven UI** — no typing required.

---

## 🎛️ Button Menu System

Send `/start`, `/menu`, or `/help` to open the **M3TAL Control Panel** — a full inline keyboard menu.

```
/start  →  Main Menu
             ├── 📊 Status       →  [System Status] [Agent Health] [Resources] [Disk] [Uptime] [Ping] [My ID]
             ├── 🐳 Docker       →  [Status] [Restart] [Stop] [Start] [Inspect] [Logs]
             │                        └── [container1] [container2] [container3] ...
             ├── 🌐 Network      →  [Public IP] [Ports] [Traefik Status]
             ├── ⚙️ System       →  [Backup] [Env Config] [Update Stacks ⚠️] [Reboot Host ⚠️]
             └── 🤖 Bot          →  [Mute Alerts] [Unmute] [Allowed Users]
```

- **Every command** is accessible via buttons — zero typing needed
- **Dangerous commands** (Reboot, Update) show a confirmation dialog before executing
- **Container actions** (Restart, Stop, Start, Inspect, Logs) present a dynamic picker with all available containers
- **Back buttons** (`⬅️ Main Menu`, `⬅️ Docker Menu`) let you navigate between menus
- All typed commands (`/docker restart radarr`, `/logs sonarr`, etc.) still work exactly as before

---

## 🔐 Security & Access Control

| Layer | Details |
| :--- | :--- |
| **User Authorization** | Only Telegram user IDs listed in `ALLOWED_USERS` (`.env`) may send commands. If empty, all users are accepted. |
| **Container Allowlist** | Container-targeted commands are restricted to containers in `ALLOWED_DOCKER_RESTARTS` plus names found in `registry.json`. |
| **Confirmation Gate** | `/reboot` and `/update` require the keyword `confirm` (typed) or a ✅ confirmation button (tapped). |
| **Secret Masking** | `/env` masks values for keys containing `TOKEN`, `SECRET`, `PASSWORD`, `KEY`, or `HASH`. |

---

## 📊 Status & Monitoring

| Command / Button | Description |
| :--- | :--- |
| `/status` | System health summary: uptime and overall status. |
| `/status agents` | Per-agent health breakdown with score (from `health.json`). |
| `/resources` | Latest CPU/RAM usage bars, top 8 containers by CPU, and health score. |
| `/disk` | Disk usage for `/` and `DATA_DIR` with visual percentage bars. |
| `/uptime` | Bot process uptime. |
| `/ping` | Connectivity test — returns `pong 🏓`. |
| `/myid` | Shows your Telegram user ID. |

---

## 🐳 Docker Management

| Command / Button | Description |
| :--- | :--- |
| `/docker` | Opens the Docker action menu (inline keyboard). |
| `/docker status` | Lists all running containers and their status. |
| `/docker restart <name>` | Restarts the named container. |
| `/docker stop <name>` | Stops the named container. |
| `/docker start <name>` | Starts a stopped container. |
| `/docker inspect <name>` | Shows image, status, start/creation time, restart policy, and port mappings. |
| `/logs` | Opens the log viewer container picker (inline keyboard). |
| `/logs <name>` | Fetches the last 30 log lines for the named service. |

---

## 🌐 Network & Routing

| Command / Button | Description |
| :--- | :--- |
| `/ip` | Fetches the host's current public IP address. |
| `/ports` | Lists all containers with published host ports. |
| `/traefik` | Traefik container status + Traefik-enabled services via Docker labels. |

---

## ⚙️ System & Maintenance

| Command / Button | Description |
| :--- | :--- |
| `/reboot confirm` | Reboots the Linux host. Requires `confirm` keyword or button confirmation. |
| `/update confirm` | Pulls latest images and recreates all stacks. Requires `confirm` keyword or button confirmation. |
| `/backup` | Creates a compressed backup of configs and state. |
| `/env` | Displays `.env` file contents with sensitive values masked. |

---

## 🤖 Bot Management

| Command / Button | Description |
| :--- | :--- |
| `/mute` | Silences proactive alert notifications for 1 hour. |
| `/unmute` | Resumes alert notifications immediately. |
| `/who` | Lists all authorized Telegram user IDs. |
| `/help` / `/start` / `/menu` | Opens the interactive button menu. |

---

## 📝 Notes

- **Case**: Commands are case-insensitive (`/Docker` = `/docker`).
- **Bot mentions**: The `@botname` suffix is stripped automatically (`/status@M3talBot` works).
- **Message TTL**: Messages older than 10 minutes are silently dropped.
- **Dual mode**: Every command works both via typed text AND via the button menu — use whichever you prefer.
