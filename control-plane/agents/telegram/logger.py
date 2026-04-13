from . import router

# M3TAL Telegram Logging Adapter (v3 Layered)
# Responsibility: Formatting and initiating the routing pipeline.

def log(msg: str):
    """Normal operations (Channel: log)."""
    text = f"⚪ <b>[LOG]</b> {msg}"
    router.route_message("log", text)

def error(msg: str):
    """Failures (Channel: error)."""
    text = f"🔴 <b>[ERROR]</b> {msg}"
    router.route_message("error", text)

def alert(msg: str):
    """Critical issues (Channel: alert)."""
    text = f"🚨 <b>[ALERT]</b> {msg}"
    router.route_message("alert", text)

def action(msg: str):
    """Command/Action feedback (Channel: action)."""
    text = f"⚡ <b>[ACTION]</b> {msg}"
    router.route_message("action", text)

def docker(msg: str):
    """Infrastructure telemetry (Channel: docker)."""
    text = f"🐳 <b>[DOCKER]</b> {msg}"
    router.route_message("docker", text)
