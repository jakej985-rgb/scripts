from __future__ import annotations

import getpass
import json
import os
from pathlib import Path
from typing import Any

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False


DEFAULT_ADMIN_USERNAME = "admin"


def resolve_users_path(default_dir: str | Path | None = None) -> Path:
    configured_path = os.environ.get("USERS_FILE")
    if configured_path:
        return Path(configured_path).expanduser()

    if default_dir is None:
        default_dir = Path(__file__).resolve().parent

    return Path(default_dir) / "users.json"


def _normalize_record(record: Any, legacy_username: str | None = None) -> dict[str, str] | None:
    if not isinstance(record, dict):
        return None

    username = str(record.get("username", legacy_username or "")).strip()
    token_hash = str(record.get("token_hash", "")).strip()
    role = str(record.get("role", "viewer")).strip() or "viewer"

    if not username or not token_hash or not token_hash.startswith("$2"):
        return None

    return {
        "username": username,
        "token_hash": token_hash,
        "role": role,
    }


def normalize_users(raw_users: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []

    if isinstance(raw_users, list):
        for record in raw_users:
            user = _normalize_record(record)
            if user:
                normalized.append(user)
    elif isinstance(raw_users, dict):
        for username, record in raw_users.items():
            user = _normalize_record(record, legacy_username=str(username))
            if user:
                normalized.append(user)

    normalized.sort(key=lambda user: user["username"])
    return normalized


def inspect_users_file(users_path: str | Path | None = None, default_dir: str | Path | None = None) -> tuple[list[dict[str, str]], str | None]:
    path = Path(users_path) if users_path is not None else resolve_users_path(default_dir)
    if not path.exists():
        return [], "missing"

    try:
        raw_users = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return [], "invalid_json"

    users = normalize_users(raw_users)
    if not users:
        return [], "invalid_users"

    return users, None


def load_users(users_path: str | Path | None = None, default_dir: str | Path | None = None) -> list[dict[str, str]]:
    users, _ = inspect_users_file(users_path=users_path, default_dir=default_dir)
    return users


def save_users(users: list[dict[str, str]], users_path: str | Path | None = None, default_dir: str | Path | None = None) -> Path:
    path = Path(users_path) if users_path is not None else resolve_users_path(default_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(users, indent=2)}\n", encoding="utf-8")
    return path


def hash_password(password: str) -> str:
    if not HAS_BCRYPT:
        raise ImportError("bcrypt module is required for password hashing. Run: pip install bcrypt")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, token_hash: str) -> bool:
    if not HAS_BCRYPT:
        # Fallback to False behavior if bcrypt is missing, but log the issue if possible
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), token_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def prompt_password(prompt_label: str = "Admin password") -> str:
    while True:
        password = getpass.getpass(f"{prompt_label}: ").strip()
        if not password:
            print("Password cannot be empty.")
            continue

        confirmation = getpass.getpass("Confirm password: ").strip()
        if password != confirmation:
            print("Passwords do not match. Try again.")
            continue

        return password


def reset_admin_user(
    users_path: str | Path | None = None,
    username: str = DEFAULT_ADMIN_USERNAME,
    password: str | None = None,
    default_dir: str | Path | None = None,
) -> Path:
    path = Path(users_path) if users_path is not None else resolve_users_path(default_dir)
    users = load_users(users_path=path)
    retained_users = [user for user in users if user["username"] != username]

    if password is None:
        password = prompt_password(f"{username} password")

    retained_users.append(
        {
            "username": username,
            "token_hash": hash_password(password),
            "role": "admin",
        }
    )
    retained_users.sort(key=lambda user: user["username"])

    return save_users(retained_users, users_path=path)


def get_role(token: str | None) -> str | None:
    if not token:
        return None

    for user in load_users():
        if verify_password(token, user["token_hash"]):
            return user.get("role", "viewer")

    return None
