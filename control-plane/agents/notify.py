#!/usr/bin/env python3
"""
M3TAL Notify Agent — Telegram Alert System
Watches anomalies.json and health_report.json, fires alerts on state changes.
"""

import os
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.paths import STATE_DIR, ANOMALIES_JSON, HEALTH_REPORT_JSON
from utils.state import load_json, save_json
from utils.guards import wrap_agent
from utils.logger import get_logger

from agents import telegram

logger = get_logger("notify")

NOTIFY_STATE_JSON = os.path.join(STATE_DIR, "notify_state.json")
MUTE_STATE_JSON = STATE_DIR / "mute_state.json"

def check_and_notify():
    # Audit Fix L1: Subprocesses must start their own Telegram worker thread
    telegram.start()
    
    if not telegram.is_available():
        return

    # --- Mute Gate (v4.0) ---
    # If the user muted alerts via /mute, skip all notifications until expiry.
    if MUTE_STATE_JSON.exists():
        try:
            mute = load_json(str(MUTE_STATE_JSON), default={})
            if mute.get("muted") and mute.get("until", 0) > time.time():
                logger.info("Alerts muted — skipping notification cycle.")
                return
            else:
                # Auto-unmute: mute expired, clean up
                MUTE_STATE_JSON.unlink(missing_ok=True)
                logger.info("Mute expired — resuming alerts.")
        except Exception as e:
            logger.warning(f"Mute state read error: {e}")

    now = int(time.time())
    state = load_json(NOTIFY_STATE_JSON, default={})

    # --- 1. Health Report Alerts ---
    report = load_json(str(HEALTH_REPORT_JSON), default={})
    verdict = report.get("verdict", "HEALTHY")
    score = report.get("score", 100)
    issues = report.get("issues", [])

    last_verdict = state.get("last_verdict", "HEALTHY")
    last_verdict_alert = state.get("last_verdict_alert_ts", 0)

    # Cooldown constants
    ALERT_VERDICTS = ["DEGRADED", "CRITICAL"]
    ALERT_COOLDOWN = 3600

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
            # Use new dynamic routing
            telegram.alert(msg)
            state["last_verdict"] = verdict
            state["last_verdict_alert_ts"] = now
            
    elif last_verdict in ALERT_VERDICTS and verdict == "HEALTHY":
        # Recovery notification
        msg = f"✅ <b>M3TAL Recovered</b>\nSystem back to HEALTHY (Score: {score}%)"
        telegram.send_main(msg)
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
            telegram.alert(msg)
            alerted_containers[target] = now

    # Clear alerted containers that are no longer anomalous
    current_targets = {i.get("target") for i in anomalies.get("issues", []) if i.get("type") == "recoverable"}
    for container in list(alerted_containers.keys()):
        if container not in current_targets:
            del alerted_containers[container]

    state["alerted_containers"] = alerted_containers
    save_json(NOTIFY_STATE_JSON, state, caller="notify")


if __name__ == "__main__":
    # Migration Note: config.telegram.validate() is now handled globally in run.py
    wrap_agent("notify", check_and_notify, interval=30)
