"""
Search engine — parses query strings and applies metadata filters from JSON.

Supported query format:
  tag:catgirl
  artist:SomeArtist
  series:ReZero
  tag:maid tag:catgirl artist:xxx
"""

import re

from app.database import get_all_image_paths
from app import metadata_manager as mm


def parse_query(query: str) -> tuple[list[str], str, str]:
    """
    Parse a query string and return (tags, artist, series).
    """
    tags: list[str] = []
    artist: str = ""
    series: str = ""

    pattern = re.compile(r'(tag|artist|series):("([^"]+)"|(\S+))', re.IGNORECASE)
    for match in pattern.finditer(query):
        prefix = match.group(1).lower()
        value = (match.group(3) or match.group(4)).strip()
        if prefix == "tag":
            tags.append(value)
        elif prefix == "artist":
            artist = value
        elif prefix == "series":
            series = value

    return tags, artist, series


def execute_search(
    query: str,
    folder_prefix: str = ""
) -> list[str]:
    """
    Execute a search given a raw query string and an optional folder prefix filter.
    Returns a sorted list of matching file paths.
    """
    tags, artist, series = parse_query(query)
    tags = [t.strip().lower() for t in tags if t.strip()]
    artist = artist.strip().lower()
    series = series.strip().lower()

    # Start from known image paths. For folder filtering, include filesystem
    # fallback so search still sees files not yet scanned into DB rows.
    if folder_prefix:
        from app.image_scanner import get_images_in_folder
        candidates = get_images_in_folder(folder_prefix)
    else:
        candidates = sorted(get_all_image_paths())

    results: list[str] = []
    for path in candidates:
        meta = mm.get_metadata(path)

        if tags:
            have = {t.lower() for t in meta.get("tags", [])}
            if not all(tag in have for tag in tags):
                continue
        if artist and artist not in str(meta.get("artist", "")).lower():
            continue
        if series and series not in str(meta.get("series", "")).lower():
            continue
        results.append(path)

    return sorted(results)
