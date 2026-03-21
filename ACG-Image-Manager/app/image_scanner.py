"""
Image scanner — recursively scans the ./images folder for supported image formats.

Two public pieces:

  ScannerThread   — full incremental DB sync (existing, unchanged).
  FolderFilterThread — lightweight thread that resolves "which images are
                       under this folder?" without blocking the UI.
  get_images_in_folder() — synchronous helper used by FolderFilterThread:
      1. Queries the DB for images whose path starts with folder_path.
      2. Falls back to a direct filesystem scan for any images that exist
         on disk but have not yet been added to the DB (e.g. scan still
         running, or user dropped files in manually).
"""

import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.database import (
    upsert_image, remove_image, get_all_image_paths, search_images
)

IMAGES_ROOT = Path(__file__).parent.parent / "images"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def scan_folder(folder: Path) -> set[str]:
    """
    Return a set of absolute file-system paths for all supported images
    found recursively under *folder*.  Uses os.walk for maximum portability.
    """
    found: set[str] = set()
    for root, _dirs, files in os.walk(folder):
        for fname in files:
            if Path(fname).suffix.lower() in SUPPORTED_EXTENSIONS:
                found.add(str(Path(root) / fname))
    return found


def get_images_in_folder(folder_path: str) -> list[str]:
    """
    Return a sorted list of all image paths that live under *folder_path*
    (including every nested subfolder).

    Strategy
    --------
    1. Ask the database for every tracked image whose path is prefixed by
       folder_path.  This is fast and preserves metadata ordering.
    2. Also do a direct filesystem scan of the same folder.
    3. Union both sets so images that exist on disk but are not yet in the
       DB (e.g. initial scan still in progress) are still shown immediately.

    The caller does not have to worry about path separator differences —
    normalisation is handled inside search_images() (database.py) and
    inside scan_folder() via pathlib.
    """
    # --- DB query (fast, O(index)) ---
    db_paths: set[str] = set(search_images(folder_prefix=folder_path))

    # --- Filesystem fallback (catches images not yet indexed) ---
    folder = Path(folder_path)
    fs_paths: set[str] = set()
    if folder.is_dir():
        fs_paths = scan_folder(folder)

    # Union: DB paths take precedence for ordering; fs extras go at the end
    all_paths = db_paths | fs_paths
    return sorted(all_paths)


# ---------------------------------------------------------------------------
# Full incremental sync thread (unchanged)
# ---------------------------------------------------------------------------

class ScannerThread(QThread):
    """Background thread that incrementally syncs the images folder with the DB."""

    progress = Signal(str)
    images_added = Signal(list)
    images_removed = Signal(list)
    finished_scan = Signal(int, int)

    def run(self) -> None:
        IMAGES_ROOT.mkdir(parents=True, exist_ok=True)

        self.progress.emit("Scanning images folder...")
        on_disk: set[str] = scan_folder(IMAGES_ROOT)

        self.progress.emit("Loading existing database entries...")
        in_db: set[str] = set(get_all_image_paths())

        new_paths = on_disk - in_db
        removed_paths = in_db - on_disk

        if new_paths:
            self.progress.emit(f"Adding {len(new_paths)} new image(s)...")
            for path in sorted(new_paths):
                upsert_image(path)
            self.images_added.emit(sorted(new_paths))

        if removed_paths:
            self.progress.emit(f"Removing {len(removed_paths)} missing image(s)...")
            for path in removed_paths:
                remove_image(path)
            self.images_removed.emit(list(removed_paths))

        self.finished_scan.emit(len(new_paths), len(removed_paths))


# ---------------------------------------------------------------------------
# Folder-filter thread — non-blocking folder click handler
# ---------------------------------------------------------------------------

class FolderFilterThread(QThread):
    """
    Resolves the list of images under a given folder in a background thread
    so the UI stays responsive even for large directory trees.

    Usage
    -----
    thread = FolderFilterThread(folder_path="/abs/path/to/folder",
                                 search_query="tag:catgirl")
    thread.results_ready.connect(image_grid.load_images)
    thread.start()

    Signals
    -------
    results_ready(list[str])  — emitted with a sorted list of matching paths
                                 when the scan is complete.
    """

    results_ready = Signal(list)

    def __init__(
        self,
        folder_path: str = "",
        search_query: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.folder_path = folder_path
        self.search_query = search_query

    def run(self) -> None:
        from app.search_engine import execute_search  # avoid circular import at module level

        if self.search_query:
            # Combined: apply text query AND folder filter together
            paths = execute_search(
                self.search_query, folder_prefix=self.folder_path
            )
        elif self.folder_path:
            # Only a folder filter: use DB + FS union helper
            paths = get_images_in_folder(self.folder_path)
        else:
            # No filter at all — return the full DB list
            paths = sorted(get_all_image_paths())

        self.results_ready.emit(paths)
