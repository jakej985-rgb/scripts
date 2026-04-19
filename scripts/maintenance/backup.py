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

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# Ensure we can find the agents package for centralized paths (Audit Fix 14)
sys.path.append(str(REPO_ROOT / "control-plane"))
from agents.utils.paths import BACKUP_DIR, REPO_ROOT as CENTRAL_ROOT

DEFAULT_DEST = BACKUP_DIR
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
                if not full_path.exists():
                    print(f"[SKIP] {target} not found")
                    continue

                if full_path.is_file():
                    if not should_exclude(full_path.name):
                        tar.add(str(full_path), arcname=target)
                else:
                    # Recursive walk for directories (Audit Fix 7)
                    for root, dirs, files in os.walk(full_path):
                        rel_root = Path(root).relative_to(repo_root)
                        # Add the directory itself
                        if not should_exclude(root):
                            tar.add(root, arcname=str(rel_root), recursive=False)
                        
                        for file in files:
                            if not should_exclude(file):
                                file_path = Path(root) / file
                                arc_name = rel_root / file
                                tar.add(str(file_path), arcname=str(arc_name))

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
        print("[BACKUP] Retention cleanup complete.")


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
