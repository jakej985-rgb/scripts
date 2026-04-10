#!/usr/bin/env python3
"""
M3TAL Backup Agent — Cross-platform disaster recovery
v1.3.0 — Python replacement for backup.sh

Creates compressed tar archives of .env, docker configs, and control-plane
state. Implements retention policy (keep last N backups).
"""

import os
import sys
import tarfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEST = Path(os.getenv("DATA_DIR", "/mnt")) / "backups" / "docker-configs"
KEEP_BACKUPS = 5

# Items to back up (relative to REPO_ROOT)
BACKUP_TARGETS = [
    ".env",
    "docker",
    "control-plane/state",
]

EXCLUDE_PATTERNS = {".log", ".pid"}


def should_exclude(path: str) -> bool:
    return any(path.endswith(ext) for ext in EXCLUDE_PATTERNS)


def create_backup(dest: Path, repo_root: Path) -> Path | None:
    """Create a timestamped tar.gz backup archive."""
    dest.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d_%H%M")
    archive_path = dest / f"backup-{timestamp}.tar.gz"

    print(f"[BACKUP] Starting backup to {dest}...")

    try:
        with tarfile.open(archive_path, "w:gz") as tar:
            for target in BACKUP_TARGETS:
                full_path = repo_root / target
                if full_path.exists():
                    tar.add(
                        str(full_path),
                        arcname=target,
                        filter=lambda ti: None if should_exclude(ti.name) else ti,
                    )
                else:
                    print(f"[SKIP] {target} not found")

        print(f"[OK] Backup created: {archive_path.name}")
        return archive_path

    except Exception as e:
        print(f"[ERROR] Backup failed: {e}")
        return None


def prune_old_backups(dest: Path, keep: int = KEEP_BACKUPS) -> None:
    """Remove old backups beyond the retention limit."""
    backups = sorted(
        dest.glob("backup-*.tar.gz"),
        key=lambda p: (p.name, p.stat().st_mtime),
        reverse=True,
    )
    for old in backups[keep:]:
        old.unlink()
        print(f"[PRUNE] Removed {old.name}")
    if len(backups) > keep:
        print(f"[BACKUP] Retention cleanup complete.")


def main() -> None:
    dest = Path(os.getenv("BACKUP_DIR", str(DEFAULT_DEST)))

    if "--dry-run" in sys.argv:
        print(f"[DRY-RUN] Would back up to: {dest}")
        for t in BACKUP_TARGETS:
            p = REPO_ROOT / t
            print(f"  {'[EXISTS]' if p.exists() else '[MISSING]'} {t}")
        return

    result = create_backup(dest, REPO_ROOT)
    if result:
        prune_old_backups(dest)


if __name__ == "__main__":
    main()
