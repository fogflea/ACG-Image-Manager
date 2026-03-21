"""Search engine with inclusion and exclusion metadata filters."""

import re

from app.database import get_all_image_paths
from app import metadata_manager as mm


def parse_query(query: str) -> tuple[list[str], list[str], str, str, str, str]:
    """
    Parse a query string.
    Returns (include_tags, exclude_tags, include_artist, exclude_artist, include_series, exclude_series)
    """
    include_tags: list[str] = []
    exclude_tags: list[str] = []
    include_artist = ""
    exclude_artist = ""
    include_series = ""
    exclude_series = ""

    pattern = re.compile(r'(-?)(tag|artist|series):("([^"]+)"|(\S+))', re.IGNORECASE)
    for match in pattern.finditer(query):
        is_exclude = bool(match.group(1))
        prefix = match.group(2).lower()
        value = (match.group(4) or match.group(5) or "").strip()

        if prefix == "tag":
            (exclude_tags if is_exclude else include_tags).append(value)
        elif prefix == "artist":
            if is_exclude:
                exclude_artist = value
            else:
                include_artist = value
        elif prefix == "series":
            if is_exclude:
                exclude_series = value
            else:
                include_series = value

    return include_tags, exclude_tags, include_artist, exclude_artist, include_series, exclude_series


def execute_search(query: str, folder_prefix: str = "") -> list[str]:
    include_tags, exclude_tags, include_artist, exclude_artist, include_series, exclude_series = parse_query(query)
    include_tags = [t.strip().lower() for t in include_tags if t.strip()]
    exclude_tags = [t.strip().lower() for t in exclude_tags if t.strip()]
    include_artist = include_artist.strip().lower()
    exclude_artist = exclude_artist.strip().lower()
    include_series = include_series.strip().lower()
    exclude_series = exclude_series.strip().lower()

    if folder_prefix:
        from app.image_scanner import get_images_in_folder
        candidates = get_images_in_folder(folder_prefix)
    else:
        candidates = sorted(get_all_image_paths())

    results: list[str] = []
    for path in candidates:
        meta = mm.get_metadata(path)
        have = {t.lower() for t in meta.get("tags", [])}
        artist = str(meta.get("artist", "")).lower()
        series = str(meta.get("series", "")).lower()

        if include_tags and not all(tag in have for tag in include_tags):
            continue
        if exclude_tags and any(tag in have for tag in exclude_tags):
            continue

        if include_artist and include_artist not in artist:
            continue
        if exclude_artist and exclude_artist in artist:
            continue

        if include_series and include_series not in series:
            continue
        if exclude_series and exclude_series in series:
            continue

        results.append(path)

    return sorted(results)
