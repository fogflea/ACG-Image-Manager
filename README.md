# Anime Image Manager — Build Instructions

## Running Directly (Development)

1. Install Python 3.11+ (https://python.org)
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the app:
   ```
   python main.py
   ```

## Building a Portable Windows EXE

### Prerequisites

- Python 3.11+ installed on Windows
- All dependencies installed (`pip install -r requirements.txt`)

### Steps

1. Open a command prompt in the `ACG-Image-Manager/` folder.

2. Run PyInstaller:
   ```
   pyinstaller build.spec
   ```

3. When complete, the portable app folder is at:
   ```
   dist/ACG-Image-Manager/
   ```

4. The folder `dist/ACG-Image-Manager/` contains everything needed.
   **Copy the entire folder** to any Windows machine — it will work without installing Python.

5. Launch by double-clicking:
   ```
   dist/ACG-Image-Manager/ACG-Image-Manager.exe
   ```

### Notes

- The entire `ACG-Image-Manager/` folder is portable — move it anywhere.
- Thumbnails are cached in `cache/thumbnails/` and regenerated automatically if missing.
- The database is in `data/database.db` — back this up to preserve your tags.
- Images are scanned from the `images/` subfolder recursively on every Refresh.
