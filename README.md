# ACG-Image-Manager

A PySide6 desktop app for managing anime image libraries with folder browsing, metadata editing, and search.

## Run in development

```bash
cd ACG-Image-Manager
pip install -r requirements.txt
python main.py
```

## Build with PyInstaller (themes included)

This project now packages the whole `themes/` directory so QSS files are available in EXE mode.

### Option 1: spec file (recommended)

```bash
cd ACG-Image-Manager
pyinstaller build.spec
```

`build.spec` includes:

- `('themes', 'themes')` in `datas`
- Runtime theme loading that uses `sys._MEIPASS/themes` when running as a bundled EXE

### Option 2: CLI `--add-data`

```bash
pyinstaller main.py --noconfirm --windowed --name AnimeImageManager --add-data "themes;themes"
```

> On Windows, the separator for `--add-data` is `;`.

## New search syntax

Search supports inclusion and exclusion filters:

- `tag:xxx` include tag
- `artist:xxx` include artist keyword
- `series:xxx` include series keyword
- `-tag:xxx` exclude tag
- `-artist:xxx` exclude artist keyword
- `-series:xxx` exclude series keyword

Examples:

- `tag:catgirl -tag:maid`
- `artist:Kyo -series:ReZero`

## Language switching (i18n)

The UI supports:

- English
- Simplified Chinese (`中文`)

Switch in menu:

- `Settings -> Language -> English / 中文`

The language preference is saved with `QSettings` and loaded on startup.

## Metadata improvements

### Autocomplete

In the metadata panel:

- Tags input has autocomplete from existing tags
- Artist input has autocomplete from existing artists
- Series input has autocomplete from existing series

### Batch delete tools

When multiple images are selected, the metadata panel provides:

- `Remove Tags...`
- `Clear Artist`
- `Clear Series`
- `Clear Description`

Each destructive action asks for confirmation and updates JSON metadata immediately.

## Folder tree context menu

Right-click any folder in the left tree and choose:

- `Open in File Explorer` (or OS equivalent on macOS/Linux)

## Image opening behavior

The internal image viewer has been replaced. Double-clicking an image now opens it using the OS default associated application (fast path for large images).
