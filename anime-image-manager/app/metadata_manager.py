"""
Metadata manager — convenience layer for reading and writing image metadata.

All write calls now propagate RuntimeError from the database layer so the
UI can display a meaningful error message instead of silently failing.

The database layer guarantees that missing image rows are upserted before
any child-table (image_tags) write, so IntegrityError on FK constraints
can no longer occur here.
"""

from app import database as db


def get_metadata(file_path: str) -> dict:
    meta = db.get_image_metadata(file_path)
    if meta is None:
        # Image exists on disk but not yet indexed — return safe defaults
        return {
            "file_path": file_path,
            "artist": "",
            "series": "",
            "description": "",
            "tags": [],
        }
    return meta


def save_artist(file_paths: list[str], artist: str) -> None:
    """
    Persist the artist value for all paths.
    db.set_artist() upserts missing image rows first so this never raises FK errors.
    Propagates RuntimeError on database failure.
    """
    db.set_artist(file_paths, artist.strip())


def save_series(file_paths: list[str], series: str) -> None:
    """
    Persist the series value for all paths.
    db.set_series() upserts missing image rows first so this never raises FK errors.
    Propagates RuntimeError on database failure.
    """
    db.set_series(file_paths, series.strip())


def save_description(file_path: str, description: str) -> None:
    """
    Persist the description for a single image.
    db.set_description() upserts the row if missing.
    Propagates RuntimeError on database failure.
    """
    db.set_description(file_path, description.strip())


def add_tags_to_images(file_paths: list[str], tags: list[str]) -> None:
    """
    Add each tag to every image in file_paths.
    db.add_tags() upserts missing image rows AND missing tag rows before
    inserting into image_tags, so FK violations cannot occur.
    Propagates RuntimeError on database failure.
    """
    clean = [t.strip().lower() for t in tags if t.strip()]
    if clean:
        db.add_tags(file_paths, clean)


def remove_tags_from_images(file_paths: list[str], tags: list[str]) -> None:
    """Remove each tag from every image in file_paths."""
    clean = [t.strip().lower() for t in tags if t.strip()]
    if clean:
        db.remove_tags(file_paths, clean)


def all_tags() -> list[str]:
    return db.get_all_tags()


def all_artists() -> list[str]:
    return db.get_all_artists()


def all_series() -> list[str]:
    return db.get_all_series()


def rename_tag(old_name: str, new_name: str) -> None:
    db.rename_tag(old_name, new_name)


def delete_tag(tag_name: str) -> None:
    db.delete_tag(tag_name)


def rename_artist(old_name: str, new_name: str) -> None:
    db.rename_artist(old_name, new_name)


def delete_artist(artist_name: str) -> None:
    db.delete_artist(artist_name)


def rename_series(old_name: str, new_name: str) -> None:
    db.rename_series(old_name, new_name)


def delete_series(series_name: str) -> None:
    db.delete_series(series_name)
