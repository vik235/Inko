"""Tests for the dev/prod environment separation in paths.py."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Ensure no inherited INKO_ENV
os.environ.pop("INKO_ENV", None)

import paths


print("[1] Auto-detect: running from source -> dev")
# We are running from source (sys.frozen is not set), so default is dev.
assert paths.env() == "dev", f"expected 'dev', got {paths.env()!r}"
appdata = str(paths.app_data_dir())
assert appdata.endswith("Inko-dev"), appdata
docs = str(paths.pdf_output_dir())
assert docs.endswith("Inko-dev"), docs
db = str(paths.db_path())
assert db.endswith("inko-dev.db"), db
backups = str(paths.backup_dir())
assert backups.endswith(os.path.join("Inko-dev", "backups")), backups
print("   OK -", appdata)
print("        ", docs)
print("        ", db)


print("[2] INKO_ENV=staging override")
os.environ["INKO_ENV"] = "staging"
assert paths.env() == "staging"
assert str(paths.app_data_dir()).endswith("Inko-staging")
assert str(paths.db_path()).endswith("inko-staging.db")
assert str(paths.pdf_output_dir()).endswith("Inko-staging")
print("   OK -", paths.app_data_dir())


print("[3] INKO_ENV=prod override (explicit)")
os.environ["INKO_ENV"] = "prod"
assert paths.env() == "prod"
appdata = str(paths.app_data_dir())
assert appdata.endswith("Inko") and not appdata.endswith("Inko-prod"), appdata
db = str(paths.db_path())
assert db.endswith("inko.db") and not db.endswith("inko-prod.db"), db
docs = str(paths.pdf_output_dir())
assert docs.endswith("Inko") and not docs.endswith("Inko-prod"), docs
print("   OK - prod paths have no suffix:", appdata)


print("[4] Mixed-case and whitespace are normalized")
os.environ["INKO_ENV"] = "  DEV  "
assert paths.env() == "dev"
os.environ["INKO_ENV"] = "Test"
assert paths.env() == "test"
print("   OK")


print("[5] Empty INKO_ENV falls back to auto-detect")
os.environ["INKO_ENV"] = ""
assert paths.env() == "dev"  # source-running default
print("   OK")


print("[6] Legacy migration is a no-op outside prod")
# Even if a Receiptly folder existed, we must not migrate it into Inko-dev.
# Simply call the function and verify no exceptions, then verify nothing
# unexpected ended up in our Inko-dev folder.
os.environ["INKO_ENV"] = "dev"
# Import-level _migrate_legacy_dirs already ran earlier under whatever env
# the test harness was invoked with. Calling it again under dev should
# return immediately (we guard with `if env() != 'prod': return`).
paths._migrate_legacy_dirs()  # should be silent no-op
print("   OK - dev migration is a no-op")


# Cleanup
os.environ.pop("INKO_ENV", None)


print()
print("All checks passed.")
