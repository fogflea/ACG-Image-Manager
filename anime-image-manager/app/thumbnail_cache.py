"""
Thumbnail cache — generates and retrieves cached thumbnails on disk.
Thumbnails are stored in ./cache/thumbnails/ keyed by a hash of the file path.
"""

import hashlib
from pathlib import Path
from typing import Optional

from PIL import Image

CACHE_DIR = Path(__file__).parent.parent / "cache" / "thumbnails"
DEFAULT_SIZE = 128


def _cache_path(file_path: str, size: int) -> Path:
    key = hashlib.md5(f"{file_path}:{size}".encode()).hexdigest()
    return CACHE_DIR / f"{key}.png"


def get_thumbnail(file_path: str, size: int = DEFAULT_SIZE) -> Optional[Path]:
    """
    Return the path to a cached thumbnail, generating it if necessary.
    Returns None if the source image cannot be read.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = _cache_path(file_path, size)

    if cached.exists():
        return cached

    try:
        with Image.open(file_path) as img:
            img.thumbnail((size, size), Image.LANCZOS)
            if img.mode in ("RGBA", "P"):
                background = Image.new("RGB", img.size, (30, 30, 30))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            img.save(str(cached), "PNG", optimize=True)
        return cached
    except Exception:
        return None


def invalidate(file_path: str) -> None:
    """Remove all cached thumbnails for a given source file."""
    for size in (64, 128, 256):
        p = _cache_path(file_path, size)
        if p.exists():
            p.unlink()
