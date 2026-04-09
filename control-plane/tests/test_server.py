"""
M3TAL Test Suite - Dashboard auth and server validation.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"

if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from auth import hash_password, inspect_users_file, reset_admin_user, save_users, verify_password


def import_server_module():
    sys.modules.pop("server", None)
    return importlib.import_module("server")


class TestUserStore:
    def test_legacy_dict_format_is_normalized(self, tmp_path):
        users_path = tmp_path / "users.json"
        users_path.write_text(
            json.dumps(
                {
                    "admin": {
                        "token_hash": hash_password("secret-pass"),
                        "role": "admin",
                    }
                }
            ),
            encoding="utf-8",
        )

        users, error = inspect_users_file(users_path=users_path)

        assert error is None
        assert users == [
            {
                "username": "admin",
                "token_hash": users[0]["token_hash"],
                "role": "admin",
            }
        ]
        assert verify_password("secret-pass", users[0]["token_hash"]) is True

    def test_reset_admin_writes_canonical_list(self, tmp_path, monkeypatch):
        users_path = tmp_path / "users.json"
        monkeypatch.setattr("auth.prompt_password", lambda prompt_label="Admin password": "brand-new-pass")

        reset_admin_user(users_path=users_path)

        saved = json.loads(users_path.read_text(encoding="utf-8"))
        assert isinstance(saved, list)
        assert saved[0]["username"] == "admin"
        assert verify_password("brand-new-pass", saved[0]["token_hash"]) is True


class TestDashboardServer:
    def _make_server(self, tmp_path, monkeypatch):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "metrics.json").write_text(json.dumps({"system": {"cpu": 5}, "containers": []}), encoding="utf-8")
        (state_dir / "health.json").write_text(json.dumps({"score": 95}), encoding="utf-8")
        (state_dir / "anomalies.json").write_text(json.dumps({"issues": []}), encoding="utf-8")
        (state_dir / "registry.json").write_text(json.dumps({"containers": ["radarr"]}), encoding="utf-8")

        users_path = tmp_path / "users.json"
        save_users(
            [
                {
                    "username": "admin",
                    "token_hash": hash_password("secret-pass"),
                    "role": "admin",
                }
            ],
            users_path=users_path,
        )

        monkeypatch.setenv("STATE_DIR", str(state_dir))
        monkeypatch.setenv("USERS_FILE", str(users_path))
        monkeypatch.setenv("DASHBOARD_SECRET", "test-secret")

        server = import_server_module()
        server.app.config["TESTING"] = True
        return server

    def test_server_uses_env_backed_paths(self, tmp_path, monkeypatch):
        server = self._make_server(tmp_path, monkeypatch)

        assert server.STATE_DIR == str(tmp_path / "state")
        assert server.USERS_JSON == str(tmp_path / "users.json")

    def test_healthz_returns_200(self, tmp_path, monkeypatch):
        server = self._make_server(tmp_path, monkeypatch)
        client = server.app.test_client()

        response = client.get("/healthz")

        assert response.status_code == 200
        assert response.get_json()["status"] == "ready"

    def test_index_redirects_unauthenticated(self, tmp_path, monkeypatch):
        server = self._make_server(tmp_path, monkeypatch)
        client = server.app.test_client()

        response = client.get("/")

        assert response.status_code == 302

    def test_login_succeeds_with_canonical_user_file(self, tmp_path, monkeypatch):
        server = self._make_server(tmp_path, monkeypatch)
        client = server.app.test_client()

        response = client.post("/login", data={"username": "admin", "password": "secret-pass"})

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")

    def test_socket_rejects_unauthenticated_clients(self, tmp_path, monkeypatch):
        server = self._make_server(tmp_path, monkeypatch)

        socket_client = server.socketio.test_client(server.app)

        assert socket_client.is_connected() is False

    def test_authenticated_socket_receives_metrics_updates(self, tmp_path, monkeypatch):
        server = self._make_server(tmp_path, monkeypatch)
        flask_client = server.app.test_client()
        login_response = flask_client.post(
            "/login",
            data={"username": "admin", "password": "secret-pass"},
        )

        assert login_response.status_code == 302

        socket_client = server.socketio.test_client(server.app, flask_test_client=flask_client)
        assert socket_client.is_connected() is True

        server.emit_metrics_update()
        received = socket_client.get_received()

        assert any(packet["name"] == "metrics_update" for packet in received)
