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

from utils.paths import STATE_DIR, ANOMALIES_JSON, HEALTH_REPORT_JSON, ENV_TELEGRAM_TOKEN, ENV_TELEGRAM_CHAT
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

logger = get_logger("notify")

TELEGRAM_TOKEN   = os.getenv(ENV_TELEGRAM_TOKEN, "")
TELEGRAM_CHAT_ID = os.getenv(ENV_TELEGRAM_CHAT, "")
NOTIFY_STATE_JSON = os.path.join(STATE_DIR, "notify_state.json")

def validate_telegram_env():
    """Strict validation for Telegram credentials (Audit fix 4.1)."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning(f"Telegram credentials missing ({ENV_TELEGRAM_TOKEN} / {ENV_TELEGRAM_CHAT}).")
        return False
    
    # 1. Whitespace check
    if TELEGRAM_TOKEN.strip() != TELEGRAM_TOKEN or TELEGRAM_CHAT_ID.strip() != TELEGRAM_CHAT_ID:
        logger.error("Telegram credentials contain hidden whitespace or newlines! Fix your .env.")
        return False
        
    # 2. Length check (most tokens are >= 40 chars)
    if len(TELEGRAM_TOKEN) < 40:
        logger.error(f"Telegram token looks truncated (Length: {len(TELEGRAM_TOKEN)}).")
        return False
        
    # 3. Quoted string check
    if (TELEGRAM_TOKEN.startswith('"') and TELEGRAM_TOKEN.endswith('"')) or \
       (TELEGRAM_TOKEN.startswith("'") and TELEGRAM_TOKEN.endswith("'")):
        logger.error("Telegram token is wrapped in quotes. Remove them from your environment configuration.")
        return False

    masked = f"{TELEGRAM_TOKEN[:5]}...{TELEGRAM_TOKEN[-5:]}"
    logger.info(f"Telegram Config Validated: Token={masked} (len={len(TELEGRAM_TOKEN)}), Chat={TELEGRAM_CHAT_ID}")
    return True

def test_telegram_connection():
    """Proactive connection check (Audit fix 4.2)."""
    if not TELEGRAM_TOKEN: return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            bot_name = data.get("result", {}).get("username", "UnknownBot")
            logger.info(f"Telegram Connection Verified: @{bot_name}")
            return True
        else:
            logger.error(f"Telegram Connection FAILED ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram Connection FAILED: {e}")
        return False

def send_telegram(message: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
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
            # Audit fix: log full body for 401/403 debugging
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
    save_json(NOTIFY_STATE_JSON, state, caller="notify")


if __name__ == "__main__":
    # Audit fix: proactive validation at boot
    if validate_telegram_env():
        test_telegram_connection()
    
    wrap_agent("notify", check_and_notify, interval=30)
