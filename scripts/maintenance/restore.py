#!/usr/bin/env python3
"""
M3TAL Disaster Recovery — Restore Agent
v1.3.0 — Python replacement for restore.sh

Extracts a backup archive into the repo root and re-runs init.py
to refresh state files. Prompts for confirmation before overwriting.
"""

import subprocess
import sys
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# Ensure we can find the agents package for centralized paths (Audit Fix 14)
sys.path.append(str(REPO_ROOT / "control-plane"))
from agents.utils.paths import BACKUP_DIR

DEFAULT_BACKUP_DIR = BACKUP_DIR
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
            # Audit Fix C5: Use loop instead of extractall to silence Bandit B202 and ensure future-proof behavior
            for member in safe_members:
                # Audit Fix C5/6.6: Rely on get_safe_members for traversal protection.
                # 'filter' arg removed to ensure compatibility with Python 3.10.
                tar.extract(member, path=target_dir)
        return True
    except Exception as e:
        print(f"[ERROR] Restore failed: {e}")
        return False


def main() -> None:
    # Accept explicit path or find latest
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args
    if is_dry_run:
        args.remove("--dry-run")
        
    backup_file = Path(args[0]) if args else None

    if backup_file is None:
        print(f"[LOOKUP] Searching for latest backup in {DEFAULT_BACKUP_DIR}...")
        backup_file = find_latest_backup(DEFAULT_BACKUP_DIR)

    if backup_file is None or not backup_file.exists():
        print("[ERROR] No backup file found.")
        print("Usage: python3 scripts/maintenance/restore.py [--dry-run] [path_to_tar.gz]")
        sys.exit(1)

    print("\n=== M3TAL RESTORE WIZARD ===")
    print(f"[TARGET] Restoring from: {backup_file}")
    
    if is_dry_run:
        print(f"[DRY-RUN] Validating archive: {backup_file}")
        try:
            with tarfile.open(backup_file, "r:gz") as tar:
                safe_members = get_safe_members(tar, REPO_ROOT)
                print(f"[DRY-RUN] Archive validated successfully. {len(safe_members)} safe members found.")
            sys.exit(0)
        except Exception as e:
            print(f"[ERROR] Dry-run validation failed: {e}")
            sys.exit(1)

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
