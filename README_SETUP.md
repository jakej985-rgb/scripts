# 🚀 One-Command Setup Guide

## 1. Clone repo

```bash
git clone https://github.com/jakej985-rgb/scripts.git
cd scripts
```

## 2. Run installer

```bash
chmod +x install.sh
./install.sh
```

## 3. Add your Telegram info

```bash
nano .env
```

Fill in:

```
BOT_TOKEN=your_token
CHAT_ID=your_id
```

## 4. Done 🎉

System will:
- Auto backup
- Auto heal
- Send alerts
- Allow Telegram control
- Monitor system

## Commands

- /status
- /restart <name>
- /logs <name>

## Notes

- Everything runs automatically via cron
- No further setup required
