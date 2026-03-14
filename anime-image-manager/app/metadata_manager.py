"""
Metadata manager — convenience layer for reading and writing image metadata.
Wraps the database module for use by UI components.
"""

from app import database as db


def get_metadata(file_path: str) -> dict:
    meta = db.get_image_metadata(file_path)
    if meta is None:
        return {"file_path": file_path, "artist": "", "series": "", "description": "", "tags": []}
    return meta


def save_artist(file_paths: list[str], artist: str) -> None:
    db.set_artist(file_paths, artist.strip())


def save_series(file_paths: list[str], series: str) -> None:
    db.set_series(file_paths, series.strip())


def save_description(file_path: str, description: str) -> None:
    db.set_description(file_path, description.strip())


def add_tags_to_images(file_paths: list[str], tags: list[str]) -> None:
    clean = [t.strip().lower() for t in tags if t.strip()]
    if clean:
        db.add_tags(file_paths, clean)


def remove_tags_from_images(file_paths: list[str], tags: list[str]) -> None:
    clean = [t.strip().lower() for t in tags if t.strip()]
    if clean:
        db.remove_tags(file_paths, clean)


def all_tags() -> list[str]:
    return db.get_all_tags()


def all_artists() -> list[str]:
    return db.get_all_artists()


def all_series() -> list[str]:
    return db.get_all_series()
