"""
M3TAL Test Suite — Init, Supervisor, Backup validation
Tests the Python replacements for the shell scripts.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add repo root to path so we can import control-plane modules
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "control-plane"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))


# =============================================================================
# init.py tests
# =============================================================================

class TestInit:
    """Validate that init.py creates the correct directory and file structure."""

    def test_scaffold_dirs(self, tmp_path, monkeypatch):
        """Dirs are created when missing."""
        import init as init_module
        monkeypatch.setattr(init_module, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(init_module, "BASE_DIR", tmp_path)
        monkeypatch.setattr(init_module, "STATE_DIR", tmp_path / "control-plane" / "state")
        monkeypatch.setattr(init_module, "LOG_DIR", tmp_path / "control-plane" / "state" / "logs")
        monkeypatch.setattr(init_module, "LOCK_DIR", tmp_path / "control-plane" / "state" / "locks")
        monkeypatch.setattr(init_module, "HEALTH_DIR", tmp_path / "control-plane" / "state" / "health")
        monkeypatch.setattr(init_module, "TMP_DIR", tmp_path / "control-plane" / "state" / "tmp")
        monkeypatch.setattr(init_module, "AGENTS_DIR", tmp_path / "control-plane" / "agents")
        monkeypatch.setattr(init_module, "DASHBOARD_DIR", tmp_path / "dashboard")
        monkeypatch.setattr(init_module, "REQUIRED_DIRS", [
            tmp_path / "control-plane" / "state",
            tmp_path / "control-plane" / "state" / "logs",
        ])

        init_module.scaffold_dirs()

        assert (tmp_path / "control-plane" / "state").is_dir()
        assert (tmp_path / "control-plane" / "state" / "logs").is_dir()

    def test_scaffold_state_resets_corrupted_json(self, tmp_path, monkeypatch):
        """Corrupted JSON files get reset to []."""
        import init as init_module
        state = tmp_path / "state"
        state.mkdir(parents=True)
        monkeypatch.setattr(init_module, "STATE_DIR", state)

        # Create a corrupted file
        corrupted = state / "metrics.json"
        corrupted.write_text("{this is not json")

        monkeypatch.setattr(init_module, "STATE_FILES", ["metrics.json"])
        init_module.scaffold_state_files()

        assert json.loads(corrupted.read_text()) == []

    def test_scaffold_state_preserves_valid_json(self, tmp_path, monkeypatch):
        """Valid JSON files are not touched."""
        import init as init_module
        state = tmp_path / "state"
        state.mkdir(parents=True)
        monkeypatch.setattr(init_module, "STATE_DIR", state)

        valid = state / "health.json"
        valid.write_text('{"score": 95}')

        monkeypatch.setattr(init_module, "STATE_FILES", ["health.json"])
        init_module.scaffold_state_files()

        assert json.loads(valid.read_text()) == {"score": 95}

    def test_scaffold_users_creates_default(self, tmp_path, monkeypatch):
        """users.json is created with an admin user when missing."""
        import init as init_module
        dashboard = tmp_path / "dashboard"
        monkeypatch.setattr(init_module, "DASHBOARD_DIR", dashboard)

        init_module.scaffold_users()

        users_path = dashboard / "users.json"
        assert users_path.exists()
        users = json.loads(users_path.read_text())
        assert len(users) == 1
        assert users[0]["username"] == "admin"
        assert users[0]["role"] == "admin"


# =============================================================================
# backup.py tests
# =============================================================================

class TestBackup:
    """Validate backup creation and retention logic."""

    def test_prune_keeps_n_backups(self, tmp_path):
        """Pruning removes archives beyond the retention limit."""
        from backup import prune_old_backups
        import time

        # Create 7 fake backup files
        for i in range(7):
            f = tmp_path / f"backup-2026-01-0{i+1}_0000.tar.gz"
            f.write_bytes(b"fake")
            # Stagger mtime so sorting works
            os.utime(f, (time.time() + i, time.time() + i))

        prune_old_backups(tmp_path, keep=5)
        remaining = list(tmp_path.glob("backup-*.tar.gz"))
        assert len(remaining) == 5


# =============================================================================
# Agent logic tests (carried over from v1.2.0)
# =============================================================================

class TestAnomalyClassification:
    """Validate anomaly classification logic."""

    def test_offline_container_is_recoverable(self):
        sys.path.insert(0, str(REPO_ROOT / "control-plane" / "agents"))
        from anomaly import classify_issue

        health = {"jellyfin": {"status": "offline"}}
        metrics = {"system": {"cpu": 10, "mem": 20}, "containers": []}

        issues = classify_issue(health, metrics)
        assert len(issues) == 1
        assert issues[0]["type"] == "recoverable"
        assert issues[0]["target"] == "jellyfin"

    def test_high_cpu_is_transient(self):
        sys.path.insert(0, str(REPO_ROOT / "control-plane" / "agents"))
        from anomaly import classify_issue

        health = {}
        metrics = {"system": {"cpu": 95, "mem": 20}, "containers": []}

        issues = classify_issue(health, metrics)
        assert any(i["type"] == "transient" for i in issues)

    def test_no_issues_on_healthy_system(self):
        sys.path.insert(0, str(REPO_ROOT / "control-plane" / "agents"))
        from anomaly import classify_issue

        health = {"radarr": {"status": "online"}}
        metrics = {"system": {"cpu": 10, "mem": 20}, "containers": []}

        issues = classify_issue(health, metrics)
        assert len(issues) == 0


class TestDecisionCooldown:
    """Validate that cooldowns prevent action flapping."""

    def test_cooldown_blocks_duplicate_restart(self):
        sys.path.insert(0, str(REPO_ROOT / "control-plane" / "agents"))
        from decision import plan_action
        import time

        issues = [{"target": "radarr", "type": "recoverable", "reason": "stopped"}]
        # Set cooldown to "just now"
        cooldowns = {"radarr": int(time.time())}

        actions, _ = plan_action(issues, cooldowns)
        assert len(actions) == 0  # Blocked by cooldown

    def test_expired_cooldown_allows_restart(self):
        sys.path.insert(0, str(REPO_ROOT / "control-plane" / "agents"))
        from decision import plan_action

        issues = [{"target": "sonarr", "type": "recoverable", "reason": "stopped"}]
        # Set cooldown to 10 minutes ago (expired)
        cooldowns = {"sonarr": 0}

        actions, _ = plan_action(issues, cooldowns)
        assert len(actions) == 1
        assert actions[0]["type"] == "restart"
