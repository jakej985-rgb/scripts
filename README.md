# M3TAL Media Server v2

Agent-based Docker orchestration system — controlled, observable, and safe.

## Architecture

```
┌──────────┐    ┌──────────┐    ┌─────────────────┐    ┌──────────────┐
│ Monitor  │ →  │ Analyzer │ →  │ Decision Engine │ →  │ Action Agent │
└──────────┘    └──────────┘    └─────────────────┘    └──────────────┘
                      ↑                   ↑                    ↑
                ┌───────────┐       ┌───────────┐       ┌─────────────┐
                │ AI Agent  │       │ Telegram  │       │ Backup Agent│
                │ (v3 safe) │       │ (v2.2)    │       │ (isolated)  │
                └───────────┘       └───────────┘       └─────────────┘
                                                              │
                                          ┌───────────────────┘
                                          ↓
                                    ┌──────────┐
                                    │Dashboard │
                                    │ (v2.1)   │
                                    └──────────┘
```

## Structure

```
/docker/
├── m3tal.sh              ← master controller (cron entry point)
├── connections.env        ← credentials + config
├── agents/
│   ├── monitor.sh         ← collects container + disk state
│   ├── analyzer.sh        ← detects unhealthy / crash loops
│   ├── decision-engine.sh ← applies rules, retry limits, queues actions
│   ├── action-agent.sh    ← executes restarts, sends alerts
│   ├── backup-agent.sh    ← daily backup with 4-snapshot rotation
│   ├── telegram-agent.sh  ← approval system + remote commands
│   └── ai-agent.sh        ← safe read-only AI recommendations
├── dashboard/
│   ├── server.py          ← Flask API + web UI server
│   └── templates/
│       └── index.html     ← live control plane dashboard
├── state/
│   ├── locks/             ← prevents concurrent runs
│   ├── cooldowns/         ← prevents action spam
│   └── retries/           ← per-container retry counters
├── logs/
├── media/                 ← media stack compose
├── maintenance/           ← maintenance stack compose
└── tattoo/                ← tattoo app compose
```

## Quick Start

1. Copy and configure env:
   ```bash
   cp /docker/connections.env.example /docker/connections.env
   nano /docker/connections.env
   ```

2. Add cron jobs:
   ```bash
   # Agent pipeline — every minute
   * * * * * /docker/m3tal.sh

   # Backups — daily at 3 AM
   0 3 * * * /docker/agents/backup-agent.sh
   ```

3. Start the dashboard:
   ```bash
   cd /docker/maintenance
   docker compose up -d dashboard
   ```
   Dashboard available at `http://your-server:8080`

## Safety Guarantees

| Layer         | Protection                          |
|---------------|-------------------------------------|
| Lock files    | Prevents overlapping agent runs     |
| Cooldowns     | 120s minimum between actions        |
| Retry limits  | Max 3 auto-restarts per container   |
| AI boundaries | Read-only, never acts directly      |
| Telegram gate | Critical actions require approval   |

## Telegram Commands

| Command              | Action                        |
|----------------------|-------------------------------|
| `status`             | Show container overview       |
| `yes`                | Approve pending action        |
| `no`                 | Reject pending action         |
| `/restart [name]`    | Restart specific container    |
| `/logs [name]`       | Tail 30 lines of container    |
| `/help`              | List all commands             |

## Enabling AI (v3)

1. Install Ollama on your server
2. Set `ENABLE_AI=true` in `connections.env`
3. Set `OLLAMA_HOST=http://localhost:11434`
4. AI will provide recommendations visible in the dashboard
