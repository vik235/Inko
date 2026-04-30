import os
import sys
from pathlib import Path

APP_NAME = "Inko"
DB_FILENAME = "inko.db"
PDF_FOLDER_NAME = "Inko"

# Legacy folder/db names — checked once on startup so existing data carries over.
LEGACY_APPDATA_NAMES = ("Receiptly", "Quickr")
LEGACY_DB_FILENAMES = ("receiptly.db", "quickr.db")
LEGACY_PDF_FOLDER_NAMES = ("Receiptly", "Quickr Receipts")


def _appdata_root() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base)


def _documents_root() -> Path:
    user = os.environ.get("USERPROFILE") or str(Path.home())
    return Path(user) / "Documents"


def _migrate_legacy_dirs() -> None:
    """Carry data forward through previous brand names."""
    appdata = _appdata_root()
    new_app = appdata / APP_NAME
    if not new_app.exists():
        for legacy in LEGACY_APPDATA_NAMES:
            old = appdata / legacy
            if old.exists():
                try:
                    old.rename(new_app)
                except OSError:
                    pass
                break
    if new_app.exists():
        target_db = new_app / DB_FILENAME
        if not target_db.exists():
            for legacy in LEGACY_DB_FILENAMES:
                p = new_app / legacy
                if p.exists():
                    try:
                        p.rename(target_db)
                    except OSError:
                        pass
                    break

    # Move files from legacy PDF folders. We move individually so a single
    # locked file (e.g. an open PDF viewer) doesn't abort the whole migration.
    docs = _documents_root()
    new_pdfs = docs / PDF_FOLDER_NAME
    for legacy in LEGACY_PDF_FOLDER_NAMES:
        old_pdfs = docs / legacy
        if not old_pdfs.exists() or old_pdfs.resolve() == new_pdfs.resolve():
            continue
        new_pdfs.mkdir(parents=True, exist_ok=True)
        for f in old_pdfs.iterdir():
            if not f.is_file():
                continue
            target = new_pdfs / f.name
            if target.exists():
                continue
            try:
                f.rename(target)
            except OSError:
                pass
        try:
            old_pdfs.rmdir()  # only succeeds if empty
        except OSError:
            pass


_migrate_legacy_dirs()


def app_data_dir() -> Path:
    p = _appdata_root() / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return app_data_dir() / DB_FILENAME


def pdf_output_dir() -> Path:
    p = _documents_root() / PDF_FOLDER_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def backup_dir() -> Path:
    p = _documents_root() / PDF_FOLDER_NAME / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def resource_path(rel: str) -> Path:
    """Resolve a bundled resource path whether running from source or PyInstaller."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).parent
    return base / rel
