"""
Entry point for ACG-Image-Manager.
Initializes the database, applies Qt settings, and launches the main window.
"""

import sys
import os
from pathlib import Path


def resource_path(relative_path):
    import sys as _sys, os as _os
    if hasattr(_sys, '_MEIPASS'):
        return _os.path.join(_sys._MEIPASS, relative_path)
    return _os.path.join(_os.path.abspath('.'), relative_path)


os.chdir(Path(__file__).parent)

from PySide6.QtWidgets import QApplication

from app.database import init_db
from app.metadata_manager import load_metadata
from ui.main_window import MainWindow


def main() -> None:
    init_db()
    load_metadata()

    app = QApplication(sys.argv)
    app.setApplicationName("ACG-Image-Manager")
    app.setApplicationVersion("1.0.0")
    app.setStyle("Fusion")

    window = MainWindow(resource_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
