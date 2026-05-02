# 🤖 M3TAL Telegram Bot — Command Reference (v4.0)

Complete reference for all **24 commands** available via the M3TAL Telegram bot.
Allows remote management, monitoring, and troubleshooting of the media server from any Telegram client.

---

## 🔐 Security & Access Control

| Layer | Details |
| :--- | :--- |
| **User Authorization** | Only Telegram user IDs listed in `ALLOWED_USERS` (`.env`) may send commands. If empty, all users are accepted. |
| **Container Allowlist** | Container-targeted commands (`restart`, `stop`, `start`, `inspect`, `logs`) are restricted to containers in `ALLOWED_DOCKER_RESTARTS` plus names found in `registry.json`. |
| **Confirmation Gate** | `/reboot` and `/update` require the keyword `confirm` as a second word to execute. |
| **Secret Masking** | `/env` masks values for keys containing `TOKEN`, `SECRET`, `PASSWORD`, `KEY`, or `HASH`. |
| **Helpful Denials** | When a command is incomplete or targets an invalid container, the bot replies with usage instructions **and** the list of available containers. |

---

## 📊 Status & Monitoring

| Command | Description |
| :--- | :--- |
| `/status` | System health summary: uptime and overall status. |
| `/status agents` | Per-agent health breakdown with score (from `health.json`). |
| `/resources` | Latest CPU/RAM usage bars, top 8 containers by CPU, and health score (from `metrics.json`). |
| `/disk` | Disk usage for `/` and `DATA_DIR` with visual percentage bars and free space. |
| `/uptime` | Bot process uptime. |
| `/ping` | Connectivity test — returns `pong 🏓`. |
| `/myid` | Shows your Telegram user ID (useful for adding to `ALLOWED_USERS`). |

---

## 🐳 Docker Management

All container-targeted sub-commands are gated by the container allowlist.
Sending `/docker` with no arguments displays the sub-command menu and available containers.

| Command | Description |
| :--- | :--- |
| `/docker status` | Lists all running containers and their Docker status string. |
| `/docker restart <name>` | Restarts the named container. |
| `/docker stop <name>` | Stops the named container. Note: blocked if the Docker Socket Proxy has `ALLOW_STOP=0`. |
| `/docker start <name>` | Starts a stopped container. |
| `/docker inspect <name>` | Shows image, status, start/creation time, restart policy, and port mappings. |
| `/logs <name>` | Fetches the last 30 log lines for the named service (output capped at ~3500 chars). |

---

## 🌐 Network & Routing

| Command | Description |
| :--- | :--- |
| `/ip` | Fetches the host's current public IP address (via `api.ipify.org`). |
| `/ports` | Lists all containers with their published host ports. |
| `/traefik` | Traefik container status + list of all Traefik-enabled services discovered via Docker labels. |

---

## ⚙️ System & Maintenance

| Command | Description |
| :--- | :--- |
| `/reboot confirm` | Reboots the Linux host after a 5-second delay. Linux only — blocked on Windows. Requires `confirm`. |
| `/update confirm` | Runs `docker compose pull` and `up -d` on every stack found in `docker/`. Requires `confirm`. |
| `/backup` | Creates a compressed backup of `.env`, `docker/` configs, and `control-plane/state/` using the built-in backup script. |
| `/env` | Displays the current `.env` file contents. Sensitive values (tokens, passwords, secrets) are masked. |

---

## 🤖 Bot Management

| Command | Description |
| :--- | :--- |
| `/mute` | Silences proactive alert notifications for 1 hour. Useful during planned maintenance. |
| `/unmute` | Resumes alert notifications immediately (clears the mute timer). |
| `/who` | Lists all authorized Telegram user IDs, or reports if access is open. |
| `/help` | Displays the full categorized command menu in chat. |

---

## 📝 Notes

- **Case**: Commands are case-insensitive (`/Docker` = `/docker`).
- **Bot mentions**: The `@botname` suffix is stripped automatically (`/status@M3talBot` works).
- **Message TTL**: Messages older than 10 minutes are silently dropped to prevent stale command replay.
- **Incomplete commands**: If you omit a required argument (e.g. `/docker restart` without a name), the bot replies with usage help **and** the list of valid container names.
