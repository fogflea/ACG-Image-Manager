"""
Entry point for Anime Image Manager.
Initializes the database, applies Qt settings, and launches the main window.
"""

import sys
import os
from pathlib import Path

os.chdir(Path(__file__).parent)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from app.database import init_db
from app.metadata_manager import load_metadata
from ui.main_window import MainWindow


def main() -> None:
    init_db()
    load_metadata()

    app = QApplication(sys.argv)
    app.setApplicationName("Anime Image Manager")
    app.setApplicationVersion("1.0.0")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
