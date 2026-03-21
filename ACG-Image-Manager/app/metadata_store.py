"""
JSON metadata storage.

Schema:
{
  "images": {
    "/abs/path/to/file": {
      "tags": ["tag1", "tag2"],
      "artist": "",
      "series": "",
      "description": ""
    }
  }
}

Writes are atomic: write temp file -> os.replace.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any


METADATA_PATH = Path(__file__).resolve().parent.parent / "data" / "metadata.json"
_LOCK = RLock()
_CACHE: dict[str, dict[str, Any]] | None = None


def _empty() -> dict[str, dict[str, Any]]:
    return {"images": {}}


def _norm(path: str) -> str:
    return path.replace("\\", "/")


def _safe_entry(entry: dict[str, Any] | None) -> dict[str, Any]:
    src = entry or {}
    tags = src.get("tags", [])
    cleaned_tags: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        t = str(tag).strip().lower()
        if t and t not in seen:
            seen.add(t)
            cleaned_tags.append(t)

    return {
        "tags": cleaned_tags,
        "artist": str(src.get("artist") or "").strip(),
        "series": str(src.get("series") or "").strip(),
        "description": str(src.get("description") or "").strip(),
    }


def load_metadata() -> dict[str, dict[str, Any]]:
    global _CACHE
    with _LOCK:
        if _CACHE is not None:
            return _CACHE

        METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not METADATA_PATH.exists():
            _CACHE = _empty()
            save_metadata(_CACHE)
            return _CACHE

        try:
            data = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = _empty()

        if not isinstance(data, dict) or "images" not in data or not isinstance(data["images"], dict):
            data = _empty()

        # Normalize entries so callers always get safe values.
        normalized: dict[str, dict[str, Any]] = {"images": {}}
        for path, meta in data["images"].items():
            normalized["images"][_norm(str(path))] = _safe_entry(meta if isinstance(meta, dict) else None)

        _CACHE = normalized
        return _CACHE


def save_metadata(data: dict[str, dict[str, Any]] | None = None) -> None:
    global _CACHE
    with _LOCK:
        if data is None:
            data = load_metadata()
        METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(prefix="metadata_", suffix=".tmp", dir=str(METADATA_PATH.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(data, tmp, ensure_ascii=False, indent=2)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_path, METADATA_PATH)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        _CACHE = data


def get_image_metadata(path: str) -> dict[str, Any]:
    data = load_metadata()
    return _safe_entry(data["images"].get(_norm(path)))


def update_image_metadata(path: str, updates: dict[str, Any]) -> None:
    data = load_metadata()
    key = _norm(path)
    current = _safe_entry(data["images"].get(key))

    merged = {
        "tags": updates.get("tags", current["tags"]),
        "artist": updates.get("artist", current["artist"]),
        "series": updates.get("series", current["series"]),
        "description": updates.get("description", current["description"]),
    }
    data["images"][key] = _safe_entry(merged)
    save_metadata(data)


def replace_all_metadata(new_data: dict[str, Any]) -> None:
    with _LOCK:
        fixed = _empty()
        images = new_data.get("images", {}) if isinstance(new_data, dict) else {}
        if isinstance(images, dict):
            for path, entry in images.items():
                fixed["images"][_norm(str(path))] = _safe_entry(entry if isinstance(entry, dict) else None)
        save_metadata(fixed)
