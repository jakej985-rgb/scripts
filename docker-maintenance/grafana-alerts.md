# Grafana → Telegram Alerts Setup

## Steps
1. Go to Grafana → Alerting
2. Create Contact Point → Webhook
3. Use Telegram bot API:

https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage

Body:
{
  "chat_id": "YOUR_CHAT_ID",
  "text": "{{ .CommonAnnotations.summary }}"
}

4. Attach to alert rules

## Example Alerts
- CPU > 80%
- Disk > 90%
- Container down
