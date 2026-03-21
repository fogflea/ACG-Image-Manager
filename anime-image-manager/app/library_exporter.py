"""
Library exporter for portable backup/transfer.

Creates a ZIP with this layout:
  database.db
  images/...
  cache/...
"""

from pathlib import Path
import zipfile


APP_ROOT = Path(__file__).resolve().parent.parent
DATA_DB = APP_ROOT / "data" / "database.db"
IMAGES_DIR = APP_ROOT / "images"
CACHE_DIR = APP_ROOT / "cache"


def _iter_files(root: Path):
    """Yield all files under *root* recursively."""
    if not root.exists():
        return
    for path in root.rglob("*"):
        if path.is_file():
            yield path


def export_library_zip(zip_path: Path) -> None:
    """
    Export database + images + cache to a ZIP file.

    Paths inside archive are relative to app root so the package remains
    portable across machines.
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if DATA_DB.exists():
            zf.write(DATA_DB, arcname="database.db")

        for file_path in _iter_files(IMAGES_DIR):
            zf.write(file_path, arcname=str(file_path.relative_to(APP_ROOT)))

        for file_path in _iter_files(CACHE_DIR):
            zf.write(file_path, arcname=str(file_path.relative_to(APP_ROOT)))
