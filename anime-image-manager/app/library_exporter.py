"""
Library exporter for portable backup/transfer.

Creates a ZIP with this layout:
  database.db
"""

from pathlib import Path
import zipfile


APP_ROOT = Path(__file__).resolve().parent.parent
DATA_DB = APP_ROOT / "data" / "database.db"


def export_library_zip(zip_path: Path) -> None:
    """
    Export metadata-only archive (database.db only).

    Keeping export metadata-only makes backups lightweight while preserving
    all tags/artist/series/description relationships.
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if DATA_DB.exists():
            zf.write(DATA_DB, arcname="database.db")
