#!/usr/bin/env python3
"""
M3TAL Disaster Recovery — Restore Agent
v1.3.0 — Python replacement for restore.sh

Extracts a backup archive into the repo root and re-runs init.py
to refresh state files. Prompts for confirmation before overwriting.
"""

import os
import subprocess
import sys
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BACKUP_DIR = Path(os.getenv("DATA_DIR", "/mnt")) / "backups" / "docker-configs"
PYTHON = sys.executable


def find_latest_backup(backup_dir: Path) -> Path | None:
    """Find the most recent backup archive by modification time."""
    backups = sorted(backup_dir.glob("backup-*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    return backups[0] if backups else None


def restore(archive_path: Path, target_dir: Path) -> bool:
    """Extract a backup archive into the target directory."""
    print(f"[RESTORE] Extracting {archive_path.name}...")
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            # Path traversal protection (Audit fix 1.4)
            try:
                tar.extractall(path=target_dir, filter='data')
            except TypeError:
                # Python < 3.12 fallback
                tar.extractall(path=target_dir)
        return True
    except Exception as e:
        print(f"[ERROR] Restore failed: {e}")
        return False


def main() -> None:
    # Accept explicit path or find latest
    backup_file = Path(sys.argv[1]) if len(sys.argv) > 1 else None

    if backup_file is None:
        print(f"[LOOKUP] Searching for latest backup in {DEFAULT_BACKUP_DIR}...")
        backup_file = find_latest_backup(DEFAULT_BACKUP_DIR)

    if backup_file is None or not backup_file.exists():
        print("[ERROR] No backup file found.")
        print("Usage: python3 scripts/restore.py [path_to_tar.gz]")
        sys.exit(1)

    print(f"\n=== M3TAL RESTORE WIZARD ===")
    print(f"[TARGET] Restoring from: {backup_file}")
    print(f"⚠️  This will OVERWRITE existing config and docker files in {REPO_ROOT}.")

    confirm = input("Continue? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        sys.exit(0)

    if restore(backup_file, REPO_ROOT):
        print("[OK] Restore complete.")
        print("[OK] Re-running init to refresh state...")
        init_script = REPO_ROOT / "control-plane" / "init.py"
        subprocess.run([PYTHON, str(init_script)], check=True)
        print("[DONE] System ready. Run 'python3 control-plane/supervisor.py' to resume.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
