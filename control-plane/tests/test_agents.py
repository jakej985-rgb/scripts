import os
import json
import pytest
from unittest.mock import patch, mock_open
import sys

# Add agents dir to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "agents"))

from agents.anomaly import classify_issue
from agents.decision import plan_action

def test_anomaly_classification():
    # Test 1: Stopped container
    health = {"qbittorrent": {"status": "offline"}}
    metrics = {"containers": []}
    issues = classify_issue(health, metrics)
    assert len(issues) > 0
    assert issues[0]["target"] == "qbittorrent"
    assert issues[0]["type"] == "recoverable"

    # Test 2: Resource Leak (CPU)
    health = {"radarr": {"status": "online"}}
    metrics = {"containers": [{"name": "radarr", "cpu": 95, "mem": 10}]}
    issues = classify_issue(health, metrics)
    assert any(i["target"] == "radarr" and i["type"] == "resource_spike" for i in issues)

def test_decision_planning():
    # Test 1: Plan restart for recoverable
    issues = [{"target": "sonarr", "type": "recoverable", "reason": "offline"}]
    actions = plan_action(issues, cooldowns={})
    assert len(actions) == 1
    assert actions[0]["type"] == "restart"
    assert actions[0]["target"] == "sonarr"

    # Test 2: Cooldown enforcement
    issues = [{"target": "sonarr", "type": "recoverable", "reason": "offline"}]
    # Mock a recent action
    cooldowns = {"sonarr": 9999999999} 
    with patch("time.time", return_value=10000000000):
        actions = plan_action(issues, cooldowns)
        assert len(actions) == 0 # Should be suppressed by cooldown

if __name__ == "__main__":
    # If run directly, run pytest
    pytest.main([__file__])
