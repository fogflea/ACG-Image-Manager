"""
Import metadata-only ZIP archives.

Archive layout:
  metadata.json
"""

from __future__ import annotations

import json
from pathlib import Path
import zipfile

from app import metadata_store


def import_library_zip(zip_path: Path) -> None:
    """
    Replace in-memory + on-disk metadata from metadata.json inside ZIP.
    """
    if not zip_path.exists():
        raise RuntimeError("Selected ZIP file does not exist.")

    with zipfile.ZipFile(zip_path, "r") as zf:
        try:
            raw = zf.read("metadata.json")
        except KeyError as exc:
            raise RuntimeError("Invalid library ZIP: metadata.json was not found.") from exc

    try:
        parsed = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Invalid metadata.json format: {exc}") from exc

    metadata_store.replace_all_metadata(parsed)
