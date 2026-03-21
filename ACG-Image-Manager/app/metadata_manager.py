"""
Metadata manager backed by JSON storage (data/metadata.json).
"""

from collections import Counter
from pathlib import Path

from app import metadata_store as store


def _norm(path: str) -> str:
    return path.replace("\\", "/")


def load_metadata() -> None:
    store.load_metadata()


def get_metadata(file_path: str) -> dict:
    meta = store.get_image_metadata(file_path)
    return {
        "file_path": file_path,
        "artist": meta.get("artist", ""),
        "series": meta.get("series", ""),
        "description": meta.get("description", ""),
        "tags": list(meta.get("tags", [])),
    }


def save_artist(file_paths: list[str], artist: str) -> None:
    artist = artist.strip()
    for fp in file_paths:
        store.update_image_metadata(fp, {"artist": artist})


def save_series(file_paths: list[str], series: str) -> None:
    series = series.strip()
    for fp in file_paths:
        store.update_image_metadata(fp, {"series": series})


def save_description(file_path: str, description: str) -> None:
    store.update_image_metadata(file_path, {"description": description.strip()})


def add_tags_to_images(file_paths: list[str], tags: list[str]) -> None:
    clean = [t.strip().lower() for t in tags if t.strip()]
    if not clean:
        return

    for fp in file_paths:
        current = get_metadata(fp)["tags"]
        merged = list(dict.fromkeys(current + clean))
        store.update_image_metadata(fp, {"tags": merged})


def remove_tags_from_images(file_paths: list[str], tags: list[str]) -> None:
    clean = {t.strip().lower() for t in tags if t.strip()}
    if not clean:
        return
    for fp in file_paths:
        current = get_metadata(fp)["tags"]
        remain = [t for t in current if t not in clean]
        store.update_image_metadata(fp, {"tags": remain})


def _all_entries() -> dict[str, dict]:
    return store.load_metadata().get("images", {})


def all_tags() -> list[str]:
    return [name for name, _count in tag_usage_counts()]


def all_artists() -> list[str]:
    return [name for name, _count in artist_usage_counts()]


def all_series() -> list[str]:
    return [name for name, _count in series_usage_counts()]


def tag_usage_counts() -> list[tuple[str, int]]:
    cnt: Counter[str] = Counter()
    for meta in _all_entries().values():
        for tag in meta.get("tags", []):
            if tag:
                cnt[str(tag).strip().lower()] += 1
    return sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))


def artist_usage_counts() -> list[tuple[str, int]]:
    cnt: Counter[str] = Counter()
    for meta in _all_entries().values():
        artist = str(meta.get("artist") or "").strip()
        if artist:
            cnt[artist] += 1
    return sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0].lower()))


def series_usage_counts() -> list[tuple[str, int]]:
    cnt: Counter[str] = Counter()
    for meta in _all_entries().values():
        series = str(meta.get("series") or "").strip()
        if series:
            cnt[series] += 1
    return sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0].lower()))


def rename_tag(old_name: str, new_name: str) -> None:
    old_name = old_name.strip().lower()
    new_name = new_name.strip().lower()
    if not old_name or not new_name or old_name == new_name:
        return

    for path, meta in _all_entries().items():
        tags = [new_name if t == old_name else t for t in meta.get("tags", [])]
        dedup = list(dict.fromkeys(tags))
        if dedup != meta.get("tags", []):
            store.update_image_metadata(path, {"tags": dedup})


def delete_tag(tag_name: str) -> None:
    tag_name = tag_name.strip().lower()
    if not tag_name:
        return
    for path, meta in _all_entries().items():
        tags = [t for t in meta.get("tags", []) if t != tag_name]
        if tags != meta.get("tags", []):
            store.update_image_metadata(path, {"tags": tags})


def rename_artist(old_name: str, new_name: str) -> None:
    old_name = old_name.strip()
    new_name = new_name.strip()
    if not old_name or not new_name or old_name == new_name:
        return
    for path, meta in _all_entries().items():
        if str(meta.get("artist") or "") == old_name:
            store.update_image_metadata(path, {"artist": new_name})


def delete_artist(artist_name: str) -> None:
    artist_name = artist_name.strip()
    if not artist_name:
        return
    for path, meta in _all_entries().items():
        if str(meta.get("artist") or "") == artist_name:
            store.update_image_metadata(path, {"artist": ""})


def rename_series(old_name: str, new_name: str) -> None:
    old_name = old_name.strip()
    new_name = new_name.strip()
    if not old_name or not new_name or old_name == new_name:
        return
    for path, meta in _all_entries().items():
        if str(meta.get("series") or "") == old_name:
            store.update_image_metadata(path, {"series": new_name})


def delete_series(series_name: str) -> None:
    series_name = series_name.strip()
    if not series_name:
        return
    for path, meta in _all_entries().items():
        if str(meta.get("series") or "") == series_name:
            store.update_image_metadata(path, {"series": ""})
