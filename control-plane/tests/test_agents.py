"""
M3TAL Test Suite — Init, Supervisor, Backup validation
Tests the Python replacements for the shell scripts.
"""

import json
import signal
import sys
import tarfile
from pathlib import Path

import pytest

# Add repo root to path so we can import control-plane modules
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
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
        """Corrupted JSON files get reset to their schema-safe defaults."""
        import init as init_module
        state = tmp_path / "state"
        state.mkdir(parents=True)
        monkeypatch.setattr(init_module, "STATE_DIR", state)

        # Create a corrupted file
        corrupted = state / "metrics.json"
        corrupted.write_text("{this is not json")

        monkeypatch.setattr(init_module, "STATE_FILE_DEFAULTS", {"metrics.json": {"system": {}, "containers": []}})
        init_module.scaffold_state_files()

        assert json.loads(corrupted.read_text()) == {"system": {}, "containers": []}

    def test_scaffold_state_preserves_valid_json(self, tmp_path, monkeypatch):
        """Valid JSON files are not touched."""
        import init as init_module
        state = tmp_path / "state"
        state.mkdir(parents=True)
        monkeypatch.setattr(init_module, "STATE_DIR", state)

        valid = state / "health.json"
        valid.write_text('{"score": 95}')

        monkeypatch.setattr(init_module, "STATE_FILE_DEFAULTS", {"health.json": {"score": 0}})
        init_module.scaffold_state_files()

        assert json.loads(valid.read_text()) == {"score": 95}

    def test_scaffold_users_prompts_interactively(self, tmp_path, monkeypatch):
        """Missing users.json is rebuilt via the shared reset helper when interactive."""
        import init as init_module
        dashboard = tmp_path / "dashboard"
        users_path = dashboard / "users.json"

        monkeypatch.setattr(init_module, "DASHBOARD_DIR", dashboard)
        monkeypatch.setattr(init_module, "resolve_users_path", lambda *_args, **_kwargs: users_path)

        def fake_reset(users_path):
            users_path.write_text(
                json.dumps([{"username": "admin", "token_hash": "$2b$12$validhash", "role": "admin"}])
            )

        monkeypatch.setattr(init_module, "reset_admin_user", fake_reset)

        init_module.scaffold_users(interactive=True)

        assert users_path.exists()
        users = json.loads(users_path.read_text())
        assert len(users) == 1
        assert users[0]["username"] == "admin"
        assert users[0]["role"] == "admin"

    def test_scaffold_users_fails_noninteractive(self, tmp_path, monkeypatch):
        import init as init_module
        dashboard = tmp_path / "dashboard"
        users_path = dashboard / "users.json"

        monkeypatch.setattr(init_module, "DASHBOARD_DIR", dashboard)
        monkeypatch.setattr(init_module, "resolve_users_path", lambda *_args, **_kwargs: users_path)

        with pytest.raises(RuntimeError):
            init_module.scaffold_users(interactive=False)


# =============================================================================
# backup.py tests
# =============================================================================

class TestBackup:
    """Validate backup creation and retention logic."""

    def test_prune_keeps_n_backups(self, tmp_path):
        """Pruning removes archives beyond the retention limit."""
        from backup import prune_old_backups

        # Create 7 fake backup files
        for i in range(7):
            f = tmp_path / f"backup-2026-01-{i+1:02d}_0000.tar.gz"
            f.write_bytes(b"fake")

        prune_old_backups(tmp_path, keep=5)
        remaining = list(tmp_path.glob("backup-*.tar.gz"))
        assert len(remaining) == 5


class TestRestore:
    def test_restore_rejects_path_traversal_archive(self, tmp_path):
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
        assert not (tmp_path / "outside.txt").exists()


class TestInstallMerge:
    def test_merge_install_tree_preserves_runtime_files_and_updates_code(self, tmp_path):
        import install as install_module

        install_dir = tmp_path / "install"
        source_dir = tmp_path / "source"
        install_dir.mkdir()
        source_dir.mkdir()

        (install_dir / ".env").write_text("DASHBOARD_SECRET=old\n")
        (install_dir / "dashboard").mkdir()
        (install_dir / "dashboard" / "users.json").write_text("runtime-users")
        (install_dir / "control-plane").mkdir()
        (install_dir / "control-plane" / "state").mkdir(parents=True)
        (install_dir / "control-plane" / "config").mkdir(parents=True)
        (install_dir / "control-plane" / "state" / "metrics.json").write_text('{"persisted": true}')
        (install_dir / "control-plane" / "config" / "cluster.yml").write_text("old-config")
        (install_dir / "control-plane" / "supervisor.py").write_text("old-supervisor")

        (source_dir / ".env").write_text("DASHBOARD_SECRET=new\n")
        (source_dir / "dashboard").mkdir()
        (source_dir / "dashboard" / "users.json").write_text("new-users")
        (source_dir / "control-plane").mkdir()
        (source_dir / "control-plane" / "state").mkdir(parents=True)
        (source_dir / "control-plane" / "config").mkdir(parents=True)
        (source_dir / "control-plane" / "state" / "metrics.json").write_text('{"persisted": false}')
        (source_dir / "control-plane" / "config" / "cluster.yml").write_text("new-config")
        (source_dir / "control-plane" / "supervisor.py").write_text("new-supervisor")

        install_module.merge_install_tree(source_dir, install_dir)

        assert (install_dir / ".env").read_text() == "DASHBOARD_SECRET=old\n"
        assert (install_dir / "dashboard" / "users.json").read_text() == "runtime-users"
        assert (install_dir / "control-plane" / "state" / "metrics.json").read_text() == '{"persisted": true}'
        assert (install_dir / "control-plane" / "config" / "cluster.yml").read_text() == "old-config"
        assert (install_dir / "control-plane" / "supervisor.py").read_text() == "new-supervisor"


class TestLeaderAndSupervisor:
    def test_elect_leader_uses_local_identity_for_local_primary(self, tmp_path, monkeypatch):
        sys.path.insert(0, str(REPO_ROOT / "control-plane" / "agents"))
        import leader as leader_module

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

    def test_handle_signal_terminates_registered_children(self, monkeypatch):
        import supervisor as supervisor_module

        class FakeProc:
            def __init__(self):
                self.terminated = False

            def terminate(self):
                self.terminated = True

        fake_proc = FakeProc()
        with supervisor_module._children_lock:
            supervisor_module._children.clear()
            supervisor_module._children.append(fake_proc)
        supervisor_module._shutdown_event.clear()

        supervisor_module._handle_signal(signal.SIGTERM, None)

        assert supervisor_module._shutdown_event.is_set() is True
        assert fake_proc.terminated is True


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

    def test_classify_issue_rejects_list_metrics(self):
        sys.path.insert(0, str(REPO_ROOT / "control-plane" / "agents"))
        from anomaly import classify_issue

        issues = classify_issue({"radarr": {"status": "online"}}, [])
        assert issues == []


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
