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

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_BACKUP_DIR = Path(os.getenv("DATA_DIR", "/mnt")) / "backups" / "docker-configs"
PYTHON = sys.executable


def find_latest_backup(backup_dir: Path) -> Path | None:
    """Find the most recent backup archive by modification time."""
    backups = sorted(backup_dir.glob("backup-*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    return backups[0] if backups else None


def get_safe_members(tar: tarfile.TarFile, target_dir: Path) -> list[tarfile.TarInfo]:
    """Validate archive members before extraction."""
    safe_members: list[tarfile.TarInfo] = []
    target_root = target_dir.resolve()

    for member in tar.getmembers():
        member_path = Path(member.name)
        if member_path.is_absolute():
            raise ValueError(f"Refusing to restore absolute path: {member.name}")

        if any(part == ".." for part in member_path.parts):
            raise ValueError(f"Refusing to restore path traversal member: {member.name}")

        if member.issym() or member.islnk():
            raise ValueError(f"Refusing to restore link member: {member.name}")

        if member.ischr() or member.isblk() or member.isfifo() or member.isdev():
            raise ValueError(f"Refusing to restore special file: {member.name}")

        resolved_member = (target_root / member_path).resolve(strict=False)
        try:
            resolved_member.relative_to(target_root)
        except ValueError as exc:
            raise ValueError(f"Refusing to restore outside target directory: {member.name}") from exc

        safe_members.append(member)

    return safe_members


def restore(archive_path: Path, target_dir: Path) -> bool:
    """Extract a backup archive into the target directory."""
    print(f"[RESTORE] Extracting {archive_path.name}...")
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            safe_members = get_safe_members(tar, target_dir)
            tar.extractall(path=target_dir, members=safe_members)
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
        print("Usage: python3 scripts/maintenance/restore.py [path_to_tar.gz]")
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
