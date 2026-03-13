"""
Urban Signal Engine — SQLite Backup Script
Creates timestamped backups and prunes old ones.

Usage:
    python scripts/backup_db.py              # one-shot backup
    python scripts/backup_db.py --loop 6h    # continuous every 6 hours

Environment:
    BACKUP_DIR       — destination (default: ./data/backups)
    BACKUP_KEEP_DAYS — retention in days (default: 30)
"""

import os
import shutil
import logging
import argparse
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] backup: %(message)s")
log = logging.getLogger("backup")

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "urban_signal.db"
DEFAULT_BACKUP_DIR = BASE_DIR / "data" / "backups"
DEFAULT_KEEP_DAYS = 30


def backup_db(
    db_path: Path = DB_PATH,
    backup_dir: Path | None = None,
    keep_days: int | None = None,
) -> Path | None:
    backup_dir = backup_dir or Path(os.getenv("BACKUP_DIR", str(DEFAULT_BACKUP_DIR)))
    keep_days = keep_days or int(os.getenv("BACKUP_KEEP_DAYS", str(DEFAULT_KEEP_DAYS)))

    if not db_path.exists():
        log.warning("DB not found at %s — skipping backup.", db_path)
        return None

    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"urban_signal_{ts}.db"

    shutil.copy2(db_path, dest)
    size_mb = dest.stat().st_size / (1024 * 1024)
    log.info("Backup created: %s (%.1f MB)", dest.name, size_mb)

    _prune_old(backup_dir, keep_days)
    return dest


def _prune_old(backup_dir: Path, keep_days: int) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    removed = 0
    for f in backup_dir.glob("urban_signal_*.db"):
        if f.stat().st_mtime < cutoff.timestamp():
            f.unlink()
            removed += 1
    if removed:
        log.info("Pruned %d backup(s) older than %d days.", removed, keep_days)


def _parse_interval(s: str) -> int:
    m = re.match(r"^(\d+)\s*(h|m|s)?$", s.strip(), re.IGNORECASE)
    if not m:
        raise ValueError(f"Invalid interval: {s!r}. Use e.g. '6h', '30m', '3600s'.")
    val, unit = int(m.group(1)), (m.group(2) or "s").lower()
    return val * {"h": 3600, "m": 60, "s": 1}[unit]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup SQLite database")
    parser.add_argument("--loop", type=str, default=None, help="Run continuously (e.g. '6h', '30m')")
    args = parser.parse_args()

    if args.loop:
        interval = _parse_interval(args.loop)
        log.info("Backup loop started — interval: %s (%ds)", args.loop, interval)
        while True:
            backup_db()
            time.sleep(interval)
    else:
        backup_db()
