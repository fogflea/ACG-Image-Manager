"""
Image scanner — recursively scans the ./images folder for supported image formats.
Designed to run in a background QThread to avoid freezing the UI.
"""

import os
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QThread, Signal

from app.database import upsert_image, remove_image, get_all_image_paths

IMAGES_ROOT = Path(__file__).parent.parent / "images"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def scan_folder(folder: Path) -> set[str]:
    """Return a set of absolute file paths for all supported images under folder."""
    found = set()
    for root, _dirs, files in os.walk(folder):
        for fname in files:
            if Path(fname).suffix.lower() in SUPPORTED_EXTENSIONS:
                found.add(str(Path(root) / fname))
    return found


class ScannerThread(QThread):
    """Background thread that incrementally syncs the images folder with the database."""

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
