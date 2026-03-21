"""
Library importer for portable restore.

Before overwrite:
- runs a DB checkpoint to flush WAL data
- backs up existing database to database_backup.db
Then replaces database.db from a selected ZIP.
"""

from pathlib import Path
import shutil
import sqlite3
import zipfile


APP_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = APP_ROOT / "data"
DATA_DB = DATA_DIR / "database.db"
BACKUP_DB = DATA_DIR / "database_backup.db"


def _safe_remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _checkpoint_and_close_db() -> None:
    """
    Force SQLite checkpoint/close cycle before file replacement.

    The app uses short-lived connections, but this guarantees WAL pages are
    flushed before import replaces the database file.
    """
    if not DATA_DB.exists():
        return

    conn = sqlite3.connect(str(DATA_DB))
    try:
        conn.execute("PRAGMA wal_checkpoint(FULL)")
    finally:
        conn.close()


def import_library_zip(zip_path: Path) -> None:
    """Import metadata-only archive and overwrite local database.db."""
    if not zip_path.exists():
        raise RuntimeError("Selected ZIP file does not exist.")

    _checkpoint_and_close_db()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DATA_DB.exists():
        shutil.copy2(DATA_DB, BACKUP_DB)

    temp_dir = APP_ROOT / ".import_tmp"
    _safe_remove(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(temp_dir)

        extracted_db = temp_dir / "database.db"
        if not extracted_db.exists():
            raise RuntimeError("Invalid library ZIP: database.db was not found.")

        _safe_remove(DATA_DB)
        _safe_remove(DATA_DB.with_suffix(".db-wal"))
        _safe_remove(DATA_DB.with_suffix(".db-shm"))
        shutil.copy2(extracted_db, DATA_DB)
    finally:
        _safe_remove(temp_dir)
