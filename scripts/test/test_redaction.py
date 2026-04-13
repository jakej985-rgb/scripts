import sys
from pathlib import Path

# Add control-plane/agents to path
repo_root = Path(__file__).resolve().parent.parent
sys.path.append(str(repo_root / "control-plane" / "agents"))

from docker_logs_agent import redact, load_secrets

def test_redaction():
    secrets = load_secrets()
    print(f"Loaded {len(secrets)} secrets for testing.")
    
    test_lines = [
        "Starting worker with token: abc123supersecretxyz",
        "Error: Invalid token ABC123SUPERSECRETXYZ (case insensitive check)",
        "User danawn22! logged in.", # From VPN_PASSWORD partial? No, VPN_PASSWORD is 'Danawn22!'
        "VPN password is Danawn22!",
        "Something unrelated: hello world"
    ]
    
    print("\n--- Redaction Test ---")
    for line in test_lines:
        redacted = redact(line, secrets)
        print(f"Original: {line.strip()}")
        print(f"Redacted: {redacted.strip()}")
        print("-" * 20)

if __name__ == "__main__":
    test_redaction()
