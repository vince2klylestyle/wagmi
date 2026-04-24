"""Gallery storage for raid media.

Stores user-uploaded photos/videos with Claude-generated vibe tags.
Index is a JSON array (not JSONL) because gallery searches need full scan.
Media files stored at data/gallery/<id>.<ext>, metadata in data/gallery/index.json.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import settings


GALLERY_DIR = settings.data_dir / "gallery"
INDEX_FILE = GALLERY_DIR / "index.json"


@dataclass
class GalleryItem:
    id: str                   # 12-char hex uuid
    filename: str             # "<id>.jpg" etc
    vibe_tags: list[str]      # ["hype", "bullish", ...]
    energy: int               # 1–5
    upload_date: str          # ISO8601 UTC
    uploader_id: Optional[int] = None


def _load_index() -> list[dict]:
    """Load gallery index from disk. Returns [] if missing."""
    if not INDEX_FILE.exists():
        return []
    try:
        with open(INDEX_FILE, 'r') as f:
            return json.load(f) or []
    except Exception:
        return []


def _save_index(items: list[dict]) -> None:
    """Save index atomically (write to .tmp then rename)."""
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = INDEX_FILE.with_suffix('.json.tmp')
    with open(tmp_path, 'w') as f:
        json.dump(items, f, indent=2)
    tmp_path.replace(INDEX_FILE)


def save(
    file_bytes: bytes,
    filename: str,
    tags: list[str],
    energy: int = 3,
    uploader_id: Optional[int] = None,
) -> GalleryItem:
    """Save file to gallery and add metadata to index.

    Args:
        file_bytes: Raw file content
        filename: Original filename (extension extracted)
        tags: Vibe tags (e.g. ["hype", "bullish"])
        energy: Energy level 1–5 (default 3)
        uploader_id: Telegram user ID (optional)

    Returns:
        GalleryItem with id, filename, tags, energy, upload_date, uploader_id
    """
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)

    # Generate 12-char hex ID
    item_id = uuid.uuid4().hex[:12]

    # Extract extension from filename
    ext = Path(filename).suffix or '.jpg'
    stored_filename = f"{item_id}{ext}"

    # Write file
    file_path = GALLERY_DIR / stored_filename
    with open(file_path, 'wb') as f:
        f.write(file_bytes)

    # Add to index
    item = GalleryItem(
        id=item_id,
        filename=stored_filename,
        vibe_tags=tags,
        energy=energy,
        upload_date=datetime.now(timezone.utc).isoformat(),
        uploader_id=uploader_id,
    )

    index = _load_index()
    index.append(asdict(item))
    _save_index(index)

    return item


def search_by_vibe(tags: list[str], limit: int = 8) -> list[GalleryItem]:
    """Find gallery items matching vibe tags.

    Returns items sorted by tag overlap count (highest first), limited to N items.
    """
    if not tags:
        return recent(limit)

    index = _load_index()

    # Score each item by tag overlap
    scored: list[tuple[int, dict]] = []
    for item_dict in index:
        item_tags = set(item_dict.get('vibe_tags', []))
        overlap = len(set(tags) & item_tags)
        if overlap > 0:
            scored.append((overlap, item_dict))

    # Sort by overlap (descending), then by upload date (newest first)
    scored.sort(key=lambda x: (-x[0], -x[1].get('upload_date', '')))

    # Convert to GalleryItem objects
    result = [
        GalleryItem(
            id=item['id'],
            filename=item['filename'],
            vibe_tags=item['vibe_tags'],
            energy=item.get('energy', 3),
            upload_date=item['upload_date'],
            uploader_id=item.get('uploader_id'),
        )
        for _, item in scored[:limit]
    ]

    return result


def recent(n: int = 20) -> list[GalleryItem]:
    """Return N most recently uploaded items."""
    index = _load_index()

    # Sort by upload_date descending (newest first)
    sorted_items = sorted(
        index,
        key=lambda x: x.get('upload_date', ''),
        reverse=True,
    )

    return [
        GalleryItem(
            id=item['id'],
            filename=item['filename'],
            vibe_tags=item['vibe_tags'],
            energy=item.get('energy', 3),
            upload_date=item['upload_date'],
            uploader_id=item.get('uploader_id'),
        )
        for item in sorted_items[:n]
    ]


def get(item_id: str) -> Optional[GalleryItem]:
    """Retrieve a single gallery item by ID."""
    index = _load_index()
    for item_dict in index:
        if item_dict['id'] == item_id:
            return GalleryItem(
                id=item_dict['id'],
                filename=item_dict['filename'],
                vibe_tags=item_dict['vibe_tags'],
                energy=item_dict.get('energy', 3),
                upload_date=item_dict['upload_date'],
                uploader_id=item_dict.get('uploader_id'),
            )
    return None


def delete(item_id: str) -> bool:
    """Delete an item from gallery (file + index)."""
    index = _load_index()
    item_dict = None
    for i, item in enumerate(index):
        if item['id'] == item_id:
            item_dict = index.pop(i)
            break

    if not item_dict:
        return False

    # Delete file
    file_path = GALLERY_DIR / item_dict['filename']
    if file_path.exists():
        file_path.unlink()

    # Save index
    _save_index(index)
    return True
