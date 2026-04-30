"""Backup + restore for the Inko SQLite database.

The DB is a single file at %APPDATA%\\Inko\\inko.db; backups are timestamped
copies in Documents\\Inko\\backups\\. We use SQLite's online backup API so
the live DB can be in use during a backup.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from paths import backup_dir, db_path


KEEP_LAST = 30
# Filenames look like inko-YYYYMMDD-HHMMSS-mmm.db (millisecond suffix to
# avoid same-second collisions). The older second-resolution form (no ms)
# is also accepted for forward compatibility.
TIMESTAMP_RE = re.compile(r"inko-(\d{8}-\d{6})(?:-(\d+))?\.db$")
TIMESTAMP_FMT = "%Y%m%d-%H%M%S"


def _new_backup_path() -> Path:
    now = datetime.now()
    stamp = now.strftime(TIMESTAMP_FMT)
    ms = now.microsecond // 1000
    return backup_dir() / f"inko-{stamp}-{ms:03d}.db"


def _parse_timestamp(filename: str) -> datetime | None:
    m = TIMESTAMP_RE.search(filename)
    if not m:
        return None
    sec_part, ms_part = m.group(1), m.group(2)
    try:
        dt = datetime.strptime(sec_part, TIMESTAMP_FMT)
    except ValueError:
        return None
    if ms_part:
        # ms may be 3-6 digits — pad to microseconds.
        micros = int(ms_part.ljust(6, "0")[:6])
        dt = dt.replace(microsecond=micros)
    return dt


def backup_now() -> Path:
    """Create a fresh backup. Returns the new backup path. Prunes old ones."""
    src_path = db_path()
    if not src_path.exists():
        # First-run edge case — there's nothing to back up yet.
        return src_path
    out = _new_backup_path()
    src = sqlite3.connect(str(src_path))
    dst = sqlite3.connect(str(out))
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()
    prune(KEEP_LAST)
    return out


def list_backups() -> list[dict]:
    """Return backups newest-first, each with name, path, size_kb, taken_at."""
    items: list[dict] = []
    for p in backup_dir().iterdir():
        if not p.is_file():
            continue
        taken = _parse_timestamp(p.name)
        if taken is None:
            continue
        items.append({
            "name": p.name,
            "path": str(p),
            "size_kb": round(p.stat().st_size / 1024, 1),
            "taken_at": taken.strftime("%Y-%m-%d %H:%M:%S"),
            "taken_at_iso": taken.isoformat(timespec="microseconds"),
        })
    items.sort(key=lambda x: x["taken_at_iso"], reverse=True)
    return items


def latest_backup() -> dict | None:
    items = list_backups()
    return items[0] if items else None


def prune(keep_last: int = KEEP_LAST) -> int:
    """Delete older backups beyond `keep_last`. Returns number deleted."""
    items = list_backups()
    deleted = 0
    for old in items[keep_last:]:
        try:
            Path(old["path"]).unlink()
            deleted += 1
        except OSError:
            pass
    return deleted


def restore_from(backup_filename: str) -> Path:
    """Replace live DB contents with the named backup. Raises on bad input."""
    name = Path(backup_filename).name  # strip any path traversal
    if not TIMESTAMP_RE.search(name):
        raise ValueError("Invalid backup filename")
    src_path = backup_dir() / name
    if not src_path.exists():
        raise FileNotFoundError(f"Backup not found: {name}")

    # Take a safety snapshot before overwriting.
    backup_now()

    src = sqlite3.connect(str(src_path))
    dst = sqlite3.connect(str(db_path()))
    try:
        with dst:
            src.backup(dst)  # writes from src into dst
    finally:
        src.close()
        dst.close()
    return src_path


def maybe_daily_backup() -> Path | None:
    """Create a backup if none exists for today. Returns path if made, else None."""
    today = datetime.now().strftime("%Y%m%d")
    for it in list_backups():
        m = TIMESTAMP_RE.search(it["name"])
        if m and m.group(1).startswith(today):
            return None
    return backup_now()
