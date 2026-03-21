"""
Library exporter for portable backup/transfer.

Creates a ZIP with this layout:
  metadata.json
"""

from pathlib import Path
import zipfile


APP_ROOT = Path(__file__).resolve().parent.parent
METADATA_JSON = APP_ROOT / "data" / "metadata.json"


def export_library_zip(zip_path: Path) -> None:
    """
    Export metadata-only archive (metadata.json only).

    Keeping export metadata-only makes backups lightweight while preserving
    all tags/artist/series/description relationships.
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if METADATA_JSON.exists():
            zf.write(METADATA_JSON, arcname="metadata.json")
