"""
M3TAL Test Suite — Init, Supervisor, Backup validation
Tests the Python replacements for the shell scripts.
"""

import json
import signal
import sys
import tarfile
from pathlib import Path


# Add repo root to path so we can import control-plane modules
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "control-plane"))
sys.path.insert(0, str(REPO_ROOT / "control-plane" / "agents"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "maintenance"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "helpers"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "test"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "config"))


# =============================================================================
# init.py tests
# =============================================================================

class TestInit:
    """Validate that init.py agents perform correctly."""

    def test_fs_agent_scaffolds_dirs(self, tmp_path, monkeypatch):
        """fs_agent creates directories when missing."""
        import init as init_module
        state_dir = tmp_path / "state"
        log_dir = state_dir / "logs"
        
        # Setup mock dependencies
        monkeypatch.setattr(init_module, "STATE_DIR", state_dir)
        monkeypatch.setattr(init_module, "LOG_DIR", log_dir)
        monkeypatch.setattr(init_module, "REQUIRED_DIRS", [state_dir, log_dir])
        
        # Ensure we don't fail on writability check in test env
        monkeypatch.setattr(init_module, "is_writable", lambda _: True)

        init_module.fs_agent()

        assert state_dir.is_dir()
        assert log_dir.is_dir()

    def test_state_agent_resets_corrupted_json(self, tmp_path, monkeypatch):
        """Corrupted JSON files get reset to their schema-safe defaults."""
        import init as init_module
        state = tmp_path / "state"
        state.mkdir(parents=True)
        monkeypatch.setattr(init_module, "STATE_DIR", state)

        # Create a corrupted file
        corrupted = state / "metrics.json"
        corrupted.write_text("{this is not json")

        defaults = {"metrics.json": {"system": {}, "containers": []}}
        monkeypatch.setattr(init_module, "STATE_FILE_DEFAULTS", defaults)
        
        init_module.state_agent()

        assert json.loads(corrupted.read_text()) == {"system": {}, "containers": []}

    def test_auth_agent_skips_in_ci(self, tmp_path, monkeypatch):
        """auth_agent should behave predictably in CI/Non-interactive environments."""
        import init as init_module
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        
        # Should return True (skip) in CI
        assert init_module.auth_agent() is True

# =============================================================================
# maintenance/backup.py & restore.py tests
# =============================================================================

class TestMaintenance:
    """Validate backup creation and retention logic."""

    def test_backup_pruning(self, tmp_path):
        """Pruning removes archives beyond the retention limit."""
        from backup import prune_old_backups

        # Create 7 fake backup files
        for i in range(7):
            f = tmp_path / f"backup-2026-01-{i+1:02d}_0000.tar.gz"
            f.write_bytes(b"fake")

        prune_old_backups(tmp_path, keep=5)
        remaining = list(tmp_path.glob("backup-*.tar.gz"))
        assert len(remaining) == 5

    def test_restore_traversal_guard(self, tmp_path):
        """Restore agent must reject path traversal attempts in archives."""
        from restore import restore

        archive_path = tmp_path / "backup.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            info = tarfile.TarInfo(name="escape.txt")
            info.type = tarfile.SYMTYPE
            info.linkname = "../../etc/passwd"
            tar.addfile(info)

        target = tmp_path / "restore-target"
        target.mkdir()

        assert restore(archive_path, target) is False

# =============================================================================
# Orchestration Tests
# =============================================================================

class TestOrchestration:
    def test_runner_signal_handling(self):
        """Verify agent runner correctly handles shutdown signals."""
        from agents import run as run_module
        
        run_module._shutdown_event.clear()
        run_module._handle_signal(signal.SIGTERM, None)
        assert run_module._shutdown_event.is_set() is True

    def test_leader_election_logic(self, tmp_path, monkeypatch):
        """Verify leader election logic handles local identification."""
        from agents import leader as leader_module

        cluster_file = tmp_path / "cluster.yml"
        cluster_file.write_text(
            "nodes:\n"
            "  control:\n"
            "    host: localhost\n"
            "    role: control\n"
        )
        leader_file = tmp_path / "leader.txt"

        monkeypatch.setattr(leader_module, "CLUSTER_YML", str(cluster_file))
        monkeypatch.setattr(leader_module, "LEADER_TXT", str(leader_file))
        monkeypatch.setattr(leader_module, "get_local_identity", lambda: "test-host")
        monkeypatch.setattr(leader_module, "get_node_identity", lambda: "test-host@127.0.0.1")
        monkeypatch.setattr(leader_module, "is_local_host", lambda host: host in {"localhost", "test-host"})

        leader_module.elect_leader()
        assert leader_file.read_text() == "test-host"

# =============================================================================
# Agent Logic Tests
# =============================================================================

class TestAgentLogic:
    """Verify anomaly detection and decision cooldowns."""

    def test_anomaly_classification(self):
        from agents.anomaly import classify_issue

        health = {"jellyfin": {"status": "offline"}}
        metrics = {"system": {"cpu": 10, "mem": 20}, "containers": []}

        issues = classify_issue(health, metrics)
        assert len(issues) == 1
        assert issues[0]["type"] == "recoverable"
        assert issues[0]["target"] == "jellyfin"

    def test_decision_cooldown(self):
        from agents.decision import plan_action
        import time

        issues = [{"target": "radarr", "type": "recoverable", "reason": "stopped"}]
        # Set cooldown to "just now"
        cooldowns = {"radarr": int(time.time()) + 10}

        actions, _ = plan_action(issues, cooldowns)
        assert len(actions) == 0  # Blocked by cooldown
