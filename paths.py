import os
import sys
from pathlib import Path

APP_NAME_BASE = "Inko"
DB_FILENAME_BASE = "inko"
PDF_FOLDER_NAME_BASE = "Inko"

# Legacy folder/db names — checked on prod startup so existing data carries over.
LEGACY_APPDATA_NAMES = ("Receiptly", "Quickr")
LEGACY_DB_FILENAMES = ("receiptly.db", "quickr.db")
LEGACY_PDF_FOLDER_NAMES = ("Receiptly", "Quickr Receipts")


# ---------- environment detection ----------

def env() -> str:
    """Return the current environment name, lowercased.

    Resolution order:
      1. INKO_ENV environment variable, if set (e.g. 'dev', 'staging', 'test').
      2. 'prod' when running as a PyInstaller-frozen build (installed .exe).
      3. 'dev' otherwise (running from source).
    """
    explicit = os.environ.get("INKO_ENV", "").strip().lower()
    if explicit:
        return explicit
    if getattr(sys, "frozen", False):
        return "prod"
    return "dev"


def _suffix() -> str:
    """Path suffix per environment: '' for prod, '-dev' / '-test' / etc."""
    e = env()
    return "" if e == "prod" else f"-{e}"


def _app_name() -> str:
    return APP_NAME_BASE + _suffix()


def _db_filename() -> str:
    return DB_FILENAME_BASE + _suffix() + ".db"


def _pdf_folder_name() -> str:
    return PDF_FOLDER_NAME_BASE + _suffix()


# ---------- filesystem roots ----------

def _appdata_root() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base)


def _documents_root() -> Path:
    user = os.environ.get("USERPROFILE") or str(Path.home())
    return Path(user) / "Documents"


# ---------- legacy migration (prod-only) ----------

def _migrate_legacy_dirs() -> None:
    """Carry data forward through previous brand names. Runs in prod only —
    we never want to silently move 'Inko' (prod data) into 'Inko-dev', etc."""
    if env() != "prod":
        return

    appdata = _appdata_root()
    new_app = appdata / APP_NAME_BASE
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
        target_db = new_app / (DB_FILENAME_BASE + ".db")
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
    new_pdfs = docs / PDF_FOLDER_NAME_BASE
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


# ---------- public path helpers ----------

def app_data_dir() -> Path:
    p = _appdata_root() / _app_name()
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return app_data_dir() / _db_filename()


def pdf_output_dir() -> Path:
    p = _documents_root() / _pdf_folder_name()
    p.mkdir(parents=True, exist_ok=True)
    return p


def backup_dir() -> Path:
    p = _documents_root() / _pdf_folder_name() / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def resource_path(rel: str) -> Path:
    """Resolve a bundled resource path whether running from source or PyInstaller."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).parent
    return base / rel
