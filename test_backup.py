"""Tests for the DB backup / restore feature."""
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from server import create_app
import db
import backup


# Reset state
db.init_db()
# Clear any prior backups so the test is deterministic.
for old in Path(backup.backup_dir()).glob("inko-*.db"):
    try:
        old.unlink()
    except OSError:
        pass

c = create_app().test_client()


print("[1] Settings save -> auto-backup created")
before = backup.list_backups()
c.post("/settings", data={
    "business_name": "Backup Test", "currency_symbol": "Rs.",
    "default_currency": "INR",
})
time.sleep(0.05)  # ensure mtime tick on systems with low resolution
after = backup.list_backups()
assert len(after) == len(before) + 1, f"expected +1 backup, got {len(after)} vs {len(before)}"
print(f"   OK - {len(after)} backups now")

print("[2] /api/backup/now creates a fresh backup")
# Wait a moment so the timestamp is distinct
time.sleep(1.1)
r = c.post("/api/backup/now")
assert r.status_code == 200
data = r.get_json()
assert data["ok"] is True
assert data["name"].startswith("inko-")
assert data["name"].endswith(".db")
print(f"   OK - {data['name']}")

print("[3] list_backups returns newest-first")
items = backup.list_backups()
assert len(items) >= 2
# Newest first
for i in range(len(items) - 1):
    assert items[i]["taken_at_iso"] >= items[i + 1]["taken_at_iso"]
print(f"   OK - {len(items)} backups, newest: {items[0]['taken_at']}")

print("[4] Settings page renders backups section")
r = c.get("/settings")
assert r.status_code == 200
body = r.data.decode("utf-8")
assert "Backups" in body
assert "Backup now" in body
assert items[0]["name"] in body
print("   OK")

print("[5] Restore endpoint replaces live DB with chosen backup")
# Change a setting in live DB
c.post("/settings", data={
    "business_name": "Changed After Backup", "currency_symbol": "$",
    "default_currency": "USD",
})
assert db.get_settings()["business_name"] == "Changed After Backup"
# Pick the newest backup which was taken BEFORE the change above
target = backup.list_backups()
# After the post above we just made another backup; we need the one before that
# So target index 1 (second-newest)
assert len(target) >= 3, f"need >=3 backups, got {len(target)}"
to_restore = target[2]  # the one with "Backup Test"
r = c.post("/api/backup/restore", data={"name": to_restore["name"]},
           follow_redirects=False)
assert r.status_code == 302, r.status_code
restored = db.get_settings()["business_name"]
assert restored == "Backup Test", f"restore did not apply, got {restored!r}"
print(f"   OK - business_name restored to {restored!r}")

print("[6] Restore takes safety snapshot first")
# After restore, we should have one MORE backup than before (the safety snap)
items_after_restore = backup.list_backups()
assert len(items_after_restore) > len(target), "no safety snapshot"
print(f"   OK - {len(items_after_restore)} backups now (added safety snapshot)")

print("[7] Restore rejects path traversal / invalid names")
r = c.post("/api/backup/restore", data={"name": "../../etc/passwd"})
assert r.status_code == 400
r = c.post("/api/backup/restore", data={"name": "not-a-backup.db"})
assert r.status_code == 400
print("   OK")

print("[8] Daily backup is idempotent within the same day")
existing = len(backup.list_backups())
result = backup.maybe_daily_backup()
assert result is None, "daily backup ran twice in same day"
assert len(backup.list_backups()) == existing
print("   OK - second call was a no-op")

print("[9] prune() respects keep_last")
# Create several quick backups
for _ in range(3):
    backup.backup_now()
    time.sleep(1.05)
n = len(backup.list_backups())
assert n >= 5
removed = backup.prune(keep_last=3)
assert removed == n - 3, f"expected {n-3} removed, got {removed}"
assert len(backup.list_backups()) == 3
print(f"   OK - pruned {removed}, kept 3")

print()
print("All checks passed.")
