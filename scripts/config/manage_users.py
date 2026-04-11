#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"

if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from auth import DEFAULT_ADMIN_USERNAME, reset_admin_user, resolve_users_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage M3TAL dashboard users.")
    parser.add_argument("--reset-admin", action="store_true", help="Create or rotate the admin user password.")
    parser.add_argument("--username", default=DEFAULT_ADMIN_USERNAME, help="Admin username to manage.")
    parser.add_argument("--users-file", default=None, help="Optional path to the users.json file.")
    args = parser.parse_args()

    if not args.reset_admin:
        parser.error("No action selected. Use --reset-admin.")

    if not sys.stdin.isatty():
        parser.error("Admin password reset requires an interactive terminal.")

    users_path = Path(args.users_file) if args.users_file else resolve_users_path(DASHBOARD_DIR)
    saved_path = reset_admin_user(users_path=users_path, username=args.username)
    print(f"[OK] Updated admin credentials in {saved_path}")


if __name__ == "__main__":
    main()
