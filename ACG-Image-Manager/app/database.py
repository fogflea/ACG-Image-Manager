"""
Database module — manages SQLite connection and all CRUD operations
for image metadata (tags, artist, series, description).

FK-safety fix
-------------
The image_tags table has:
    FOREIGN KEY (file_path) REFERENCES images(file_path)

If an image was found on disk via the filesystem fallback in
get_images_in_folder() but the initial DB scan hasn't registered it yet,
its file_path does not exist in the images table.  Any write to image_tags
for that path therefore raises:
    sqlite3.IntegrityError: FOREIGN KEY constraint failed

Fix: every write function now calls _ensure_images_exist() first, which
does a bulk INSERT OR IGNORE into images for all target paths before any
child-table update.  This is safe — INSERT OR IGNORE leaves existing rows
untouched; it only adds the row if it is truly missing.

All write operations are wrapped in a single transaction so a partial
failure leaves the database unchanged.
"""

import sqlite3
import os
from pathlib import Path
from typing import Optional


DB_PATH = Path(__file__).parent.parent / "data" / "database.db"
_OPEN_CONNECTIONS: set[sqlite3.Connection] = set()


def _prune_closed_connections() -> None:
    """
    Drop already-closed handles from the registry.
    """
    closed: list[sqlite3.Connection] = []
    for conn in _OPEN_CONNECTIONS:
        try:
            conn.execute("SELECT 1")
        except sqlite3.Error:
            closed.append(conn)
    for conn in closed:
        _OPEN_CONNECTIONS.discard(conn)


def _norm(path: str) -> str:
    """Normalise a path to forward slashes and strip any trailing separator."""
    return path.replace("\\", "/").rstrip("/")


def get_connection() -> sqlite3.Connection:
    _prune_closed_connections()
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _OPEN_CONNECTIONS.add(conn)
    return conn


def close_database() -> None:
    """
    Close every tracked SQLite connection to release OS file locks.

    Import/replace flows call this before overwriting database.db to avoid
    WinError 32 on Windows when another live connection still holds handles.
    """
    stale = list(_OPEN_CONNECTIONS)
    for conn in stale:
        try:
            conn.close()
        except sqlite3.Error:
            # Best-effort cleanup: a closing failure should not block import.
            pass
    _OPEN_CONNECTIONS.clear()


def reopen_database() -> None:
    """
    Re-open DB after import replacement so startup-time pragmas are re-applied.
    """
    with get_connection() as conn:
        conn.execute("SELECT 1")


def init_db() -> None:
    os.makedirs(DB_PATH.parent, exist_ok=True)
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS images (
                file_path TEXT PRIMARY KEY,
                artist TEXT DEFAULT '',
                series TEXT DEFAULT '',
                description TEXT DEFAULT '',
                date_added TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL COLLATE NOCASE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS image_tags (
                file_path TEXT NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (file_path, tag_id),
                FOREIGN KEY (file_path) REFERENCES images(file_path) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_images_artist ON images(artist)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_images_series ON images(series)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_image_tags_fp ON image_tags(file_path)")
        conn.commit()


# ---------------------------------------------------------------------------
# FK-safety helper
# ---------------------------------------------------------------------------

def _ensure_images_exist(conn: sqlite3.Connection, file_paths: list[str]) -> None:
    """
    Guarantee every path in file_paths has a row in the images table.

    Uses INSERT OR IGNORE so existing rows (with all their metadata) are
    never overwritten.  This prevents FK constraint violations when editing
    metadata for images that exist on disk but haven't been indexed yet.
    """
    conn.executemany(
        "INSERT OR IGNORE INTO images (file_path) VALUES (?)",
        [(fp,) for fp in file_paths],
    )


# ---------------------------------------------------------------------------
# Basic image row management
# ---------------------------------------------------------------------------

def upsert_image(file_path: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO images (file_path) VALUES (?)",
            (file_path,),
        )
        conn.commit()


def remove_image(file_path: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM images WHERE file_path = ?", (file_path,))
        conn.commit()


def get_image_metadata(file_path: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM images WHERE file_path = ?", (file_path,)
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        # Keep UI-safe string values even if older/newer DB rows contain NULL.
        data["artist"] = data.get("artist") or ""
        data["series"] = data.get("series") or ""
        data["description"] = data.get("description") or ""
        tags = conn.execute(
            """SELECT t.name FROM tags t
               JOIN image_tags it ON t.id = it.tag_id
               WHERE it.file_path = ?
               ORDER BY t.name""",
            (file_path,),
        ).fetchall()
        data["tags"] = [r["name"] for r in tags]
        return data


# ---------------------------------------------------------------------------
# Metadata writers — all call _ensure_images_exist() first
# ---------------------------------------------------------------------------

def set_artist(file_paths: list[str], artist: str) -> None:
    """
    Set the artist field for every path in file_paths.

    Upserts missing image rows first so the UPDATE always affects at
    least one row, even for images not yet indexed by the scanner.
    """
    if not file_paths:
        return
    try:
        with get_connection() as conn:
            _ensure_images_exist(conn, file_paths)          # FK-safety
            conn.executemany(
                "UPDATE images SET artist = ? WHERE file_path = ?",
                [(artist, fp) for fp in file_paths],
            )
            conn.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to save artist: {exc}") from exc


def set_series(file_paths: list[str], series: str) -> None:
    """
    Set the series field for every path in file_paths.

    Upserts missing image rows first so the UPDATE always affects at
    least one row, even for images not yet indexed by the scanner.
    """
    if not file_paths:
        return
    try:
        with get_connection() as conn:
            _ensure_images_exist(conn, file_paths)          # FK-safety
            conn.executemany(
                "UPDATE images SET series = ? WHERE file_path = ?",
                [(series, fp) for fp in file_paths],
            )
            conn.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to save series: {exc}") from exc


def set_description(file_path: str, description: str) -> None:
    """Set the description for a single image. Upserts the row if missing."""
    try:
        with get_connection() as conn:
            _ensure_images_exist(conn, [file_path])         # FK-safety
            conn.execute(
                "UPDATE images SET description = ? WHERE file_path = ?",
                (description, file_path),
            )
            conn.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to save description: {exc}") from exc


# ---------------------------------------------------------------------------
# Tag helpers
# ---------------------------------------------------------------------------

def _get_or_create_tag(conn: sqlite3.Connection, tag_name: str) -> int:
    """Return the tag id, creating the tag row if it doesn't exist yet."""
    tag_name = tag_name.strip().lower()
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,))
    return cur.lastrowid


def add_tags(file_paths: list[str], tags: list[str]) -> None:
    """
    Add each tag to every image in file_paths.

    Steps (all inside one transaction):
      1. Upsert every image row — prevents FK violation on image_tags.
      2. For each tag, get-or-create its row in the tags table.
      3. Bulk-insert into image_tags (INSERT OR IGNORE = idempotent).
    """
    if not file_paths or not tags:
        return
    try:
        with get_connection() as conn:
            # Step 1 — guarantee parent rows exist
            _ensure_images_exist(conn, file_paths)

            for tag_name in tags:
                tag_name = tag_name.strip().lower()
                if not tag_name:
                    continue
                # Step 2 — guarantee tag row exists
                tag_id = _get_or_create_tag(conn, tag_name)
                # Step 3 — link images to tag
                conn.executemany(
                    "INSERT OR IGNORE INTO image_tags (file_path, tag_id) VALUES (?, ?)",
                    [(fp, tag_id) for fp in file_paths],
                )
            conn.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to add tags: {exc}") from exc


def remove_tags(file_paths: list[str], tags: list[str]) -> None:
    """Remove each tag from every image in file_paths."""
    if not file_paths or not tags:
        return
    try:
        with get_connection() as conn:
            for tag_name in tags:
                tag_name = tag_name.strip().lower()
                row = conn.execute(
                    "SELECT id FROM tags WHERE name = ?", (tag_name,)
                ).fetchone()
                if not row:
                    continue
                conn.executemany(
                    "DELETE FROM image_tags WHERE file_path = ? AND tag_id = ?",
                    [(fp, row["id"]) for fp in file_paths],
                )
            conn.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to remove tags: {exc}") from exc


def rename_tag(old_name: str, new_name: str) -> None:
    """
    Rename a tag while preserving all image links.

    If new_name already exists, links from old_name are merged into the
    existing new_name tag and the old tag row is removed.
    """
    old_name = old_name.strip().lower()
    new_name = new_name.strip().lower()
    if not old_name or not new_name or old_name == new_name:
        return

    try:
        with get_connection() as conn:
            old_row = conn.execute(
                "SELECT id FROM tags WHERE name = ?",
                (old_name,),
            ).fetchone()
            if not old_row:
                return

            new_row = conn.execute(
                "SELECT id FROM tags WHERE name = ?",
                (new_name,),
            ).fetchone()

            if new_row:
                # Merge: copy links to the existing new tag, then drop old links/tag.
                conn.execute(
                    """
                    INSERT OR IGNORE INTO image_tags (file_path, tag_id)
                    SELECT file_path, ? FROM image_tags WHERE tag_id = ?
                    """,
                    (new_row["id"], old_row["id"]),
                )
                conn.execute(
                    "DELETE FROM image_tags WHERE tag_id = ?",
                    (old_row["id"],),
                )
                conn.execute(
                    "DELETE FROM tags WHERE id = ?",
                    (old_row["id"],),
                )
            else:
                conn.execute(
                    "UPDATE tags SET name = ? WHERE id = ?",
                    (new_name, old_row["id"]),
                )
            conn.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to rename tag: {exc}") from exc


def delete_tag(tag_name: str) -> None:
    """
    Remove a tag from all images and delete the tag row itself.
    """
    tag_name = tag_name.strip().lower()
    if not tag_name:
        return

    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM tags WHERE name = ?",
                (tag_name,),
            ).fetchone()
            if not row:
                return

            conn.execute("DELETE FROM image_tags WHERE tag_id = ?", (row["id"],))
            conn.execute("DELETE FROM tags WHERE id = ?", (row["id"],))
            conn.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to delete tag: {exc}") from exc


def rename_artist(old_name: str, new_name: str) -> None:
    """Rename artist text on all image rows that reference old_name."""
    old_name = old_name.strip()
    new_name = new_name.strip()
    if not old_name or not new_name or old_name == new_name:
        return
    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE images SET artist = ? WHERE artist = ?",
                (new_name, old_name),
            )
            conn.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to rename artist: {exc}") from exc


def delete_artist(artist_name: str) -> None:
    """
    Remove artist reference from all images.

    The current schema stores artist inline on images (no separate artists
    table), so "delete artist" means nulling the value on all matching rows.
    """
    artist_name = artist_name.strip()
    if not artist_name:
        return
    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE images SET artist = NULL WHERE artist = ?",
                (artist_name,),
            )
            conn.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to delete artist: {exc}") from exc


def rename_series(old_name: str, new_name: str) -> None:
    """Rename series text on all image rows that reference old_name."""
    old_name = old_name.strip()
    new_name = new_name.strip()
    if not old_name or not new_name or old_name == new_name:
        return
    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE images SET series = ? WHERE series = ?",
                (new_name, old_name),
            )
            conn.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to rename series: {exc}") from exc


def delete_series(series_name: str) -> None:
    """
    Remove series reference from all images.

    The current schema stores series inline on images (no separate series
    table), so "delete series" means nulling the value on all matching rows.
    """
    series_name = series_name.strip()
    if not series_name:
        return
    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE images SET series = NULL WHERE series = ?",
                (series_name,),
            )
            conn.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to delete series: {exc}") from exc


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def get_all_tags() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT name FROM tags ORDER BY name").fetchall()
        return [r["name"] for r in rows]


def get_tag_usage_counts() -> list[tuple[str, int]]:
    """
    Return [(tag_name, usage_count), ...], sorted by most-used first.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT t.name AS name, COUNT(it.file_path) AS usage_count
            FROM tags t
            LEFT JOIN image_tags it ON it.tag_id = t.id
            GROUP BY t.id, t.name
            ORDER BY usage_count DESC, t.name ASC
            """
        ).fetchall()
        return [(r["name"], int(r["usage_count"])) for r in rows]


def get_all_artists() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT artist FROM images WHERE artist != '' ORDER BY artist"
        ).fetchall()
        return [r["artist"] for r in rows]


def get_artist_usage_counts() -> list[tuple[str, int]]:
    """
    Return [(artist_name, usage_count), ...], sorted by most-used first.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT artist AS name, COUNT(*) AS usage_count
            FROM images
            WHERE artist IS NOT NULL AND artist != ''
            GROUP BY artist
            ORDER BY usage_count DESC, artist ASC
            """
        ).fetchall()
        return [(r["name"], int(r["usage_count"])) for r in rows]


def get_all_series() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT series FROM images WHERE series != '' ORDER BY series"
        ).fetchall()
        return [r["series"] for r in rows]


def get_series_usage_counts() -> list[tuple[str, int]]:
    """
    Return [(series_name, usage_count), ...], sorted by most-used first.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT series AS name, COUNT(*) AS usage_count
            FROM images
            WHERE series IS NOT NULL AND series != ''
            GROUP BY series
            ORDER BY usage_count DESC, series ASC
            """
        ).fetchall()
        return [(r["name"], int(r["usage_count"])) for r in rows]


def get_all_image_paths() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT file_path FROM images").fetchall()
        return [r["file_path"] for r in rows]


def search_images(
    tags: list[str] = None,
    artist: str = "",
    series: str = "",
    folder_prefix: str = "",
) -> list[str]:
    with get_connection() as conn:
        query = "SELECT DISTINCT i.file_path FROM images i"
        conditions: list[str] = []
        params: list = []

        if tags:
            for idx, tag in enumerate(tags):
                alias   = f"it{idx}"
                alias_t = f"t{idx}"
                query += f" JOIN image_tags {alias} ON i.file_path = {alias}.file_path"
                query += (
                    f" JOIN tags {alias_t}"
                    f" ON {alias}.tag_id = {alias_t}.id AND {alias_t}.name = ?"
                )
                params.append(tag.strip().lower())

        if artist:
            conditions.append("i.artist LIKE ?")
            params.append(f"%{artist}%")

        if series:
            conditions.append("i.series LIKE ?")
            params.append(f"%{series}%")

        if folder_prefix:
            # Normalise both sides to forward slashes so that paths stored
            # with backslashes (Windows os.walk) still match the forward-slash
            # path emitted by QFileSystemModel.  The trailing '/% ' boundary
            # prevents matching sibling folders with the same name prefix.
            norm = _norm(folder_prefix)
            conditions.append("REPLACE(i.file_path, '\\', '/') LIKE ?")
            params.append(f"{norm}/%")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY i.file_path"

        rows = conn.execute(query, params).fetchall()
        return [r["file_path"] for r in rows]
