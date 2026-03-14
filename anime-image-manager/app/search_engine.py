"""
Search engine — parses query strings and delegates to the database layer.

Supported query format:
  tag:catgirl
  artist:SomeArtist
  series:ReZero
  tag:maid tag:catgirl artist:xxx
"""

import re
from app.database import search_images


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
    return search_images(
        tags=tags or None,
        artist=artist,
        series=series,
        folder_prefix=folder_prefix
    )
