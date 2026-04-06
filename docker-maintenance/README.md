# Docker Self-Healing + Telegram Control System

Includes:
- Auto backup (smart filtered)
- Auto heal containers
- Telegram alerts + control
- Log monitoring
- System stats

## Setup
1. Edit notify.sh with BOT_TOKEN + CHAT_ID
2. Make scripts executable:
```bash
chmod +x *.sh
```
3. Add to cron

## Telegram Commands
- /status
- /restart <container>
- /logs <container>
