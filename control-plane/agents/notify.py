#!/usr/bin/env python3
"""
M3TAL Notify Agent — Telegram Alert System
Watches anomalies.json and health_report.json, fires alerts on state changes.
"""

import os
import sys
import time
import requests
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR, ANOMALIES_JSON, HEALTH_REPORT_JSON
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("notify")

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
NOTIFY_STATE_JSON = os.path.join(STATE_DIR, "notify_state.json")

# Only alert when these verdicts are NEW (don't spam)
ALERT_VERDICTS = {"WARNING", "CRITICAL"}

# Cooldown per alert type (seconds) — prevents duplicate spam
ALERT_COOLDOWN = 300  # 5 minutes


def send_telegram(message: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials missing (TELEGRAM_TOKEN / TELEGRAM_CHAT_ID). Skipping.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info("Telegram alert sent.")
            return True
        else:
            logger.error(f"Telegram API error {resp.status_code}: {resp.text}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error("Telegram send failed: No network connectivity.")
        return False
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


def check_and_notify():
    now = int(time.time())
    state = load_json(NOTIFY_STATE_JSON, default={})

    # --- 1. Health Report Alerts ---
    report = load_json(str(HEALTH_REPORT_JSON), default={})
    verdict = report.get("verdict", "HEALTHY")
    score = report.get("score", 100)
    issues = report.get("issues", [])

    last_verdict = state.get("last_verdict", "HEALTHY")
    last_verdict_alert = state.get("last_verdict_alert_ts", 0)

    if verdict in ALERT_VERDICTS:
        # Alert if: verdict changed OR cooldown expired
        if verdict != last_verdict or (now - last_verdict_alert) > ALERT_COOLDOWN:
            emoji = "🔴" if verdict == "CRITICAL" else "🟡"
            issue_lines = "\n".join(f"  • {i}" for i in issues[:5]) or "  (none reported)"
            msg = (
                f"{emoji} <b>M3TAL Health {verdict}</b>\n"
                f"Score: <b>{score}%</b>\n\n"
                f"<b>Issues:</b>\n{issue_lines}"
            )
            if send_telegram(msg):
                state["last_verdict"] = verdict
                state["last_verdict_alert_ts"] = now
    elif last_verdict in ALERT_VERDICTS and verdict == "HEALTHY":
        # Recovery notification
        msg = f"✅ <b>M3TAL Recovered</b>\nSystem back to HEALTHY (Score: {score}%)"
        if send_telegram(msg):
            state["last_verdict"] = verdict
            state["last_verdict_alert_ts"] = now

    # --- 2. Container Down Alerts ---
    anomalies = load_json(str(ANOMALIES_JSON), default={"issues": []})
    alerted_containers = state.get("alerted_containers", {})

    for issue in anomalies.get("issues", []):
        if issue.get("type") != "recoverable":
            continue
        target = issue.get("target", "unknown")
        reason = issue.get("reason", "unknown")
        last_alert_ts = alerted_containers.get(target, 0)

        if (now - last_alert_ts) > ALERT_COOLDOWN:
            msg = (
                f"🚨 <b>Container Down</b>\n"
                f"<code>{target}</code>\n"
                f"Reason: {reason}\n"
                f"M3TAL is attempting recovery."
            )
            if send_telegram(msg):
                alerted_containers[target] = now

    # Clear alerted containers that are no longer anomalous
    current_targets = {i.get("target") for i in anomalies.get("issues", []) if i.get("type") == "recoverable"}
    for container in list(alerted_containers.keys()):
        if container not in current_targets:
            del alerted_containers[container]

    state["alerted_containers"] = alerted_containers
    save_json(NOTIFY_STATE_JSON, state)


if __name__ == "__main__":
    wrap_agent("notify", check_and_notify, interval=30)
