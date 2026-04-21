r"""Discover and index local TG media downloads.

Scans designated folders (e.g., TG backup export, local downloads) and
registers media as reference library entries.

Patterns:
  - Downloads go to: C:\Users\vince\Downloads\TG_*
  - Backups go to: C:\Users\vince\WAGMI\memegine-inbox\...
  - Manual copies go to: data/local_tg_media/

For each found item, create a reference entry with:
  - id: sha256(filepath)
  - filename: relative to project references_dir (or store full path)
  - tags: infer from folder name + content type
  - notes: auto-populated with file size, date
  - source: "local:path"
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Optional

from .config import settings


def _hash_file(path: Path) -> str:
    """SHA256 hash of file for unique ID."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()[:16]


def infer_tags_from_folder(folder_name: str) -> list[str]:
    """Guess semantic tags from folder name.

    Examples:
      'kilroy' → ['kilroy', 'sticker']
      'spongify' → ['spong', 'face', 'reference']
      'tg_backup_crypto' → ['crypto', 'twitter']
    """
    tags = []
    lower = folder_name.lower()

    # Brand tags
    if 'kilroy' in lower:
        tags.extend(['kilroy', 'sticker'])
    if 'spong' in lower:
        tags.extend(['spong', 'reference', 'monkey'])
    if 'motion' in lower:
        tags.extend(['motion', 'video', 'footage'])

    # Topic tags
    for word in lower.split('_'):
        if word in ('crypto', 'trading', 'trader', 'wallet', 'chart', 'pump', 'rug'):
            tags.append(word)

    return list(set(tags))


def scan_folder(folder: Path, brand: str, tag_prefix: Optional[str] = None) -> list[dict]:
    """Scan a folder for media files. Return reference entries.

    Args:
      folder: Path to scan
      brand: Which project ('kilroy', 'motion', 'spong')
      tag_prefix: Optional tag to add to all entries (e.g., 'kilroy-raid')

    Returns:
      List of reference index entries
    """
    entries = []
    if not folder.exists():
        return entries

    inferred_tags = infer_tags_from_folder(folder.name)
    if tag_prefix:
        inferred_tags.insert(0, tag_prefix)

    for f in folder.rglob("*"):
        if not f.is_file():
            continue

        # Skip non-media
        suffix = f.suffix.lower()
        if suffix not in ('.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov', '.webm', '.mkv'):
            continue

        # Create entry
        file_id = _hash_file(f)
        size_mb = f.stat().st_size / (1024 * 1024)

        entry = {
            "id": file_id,
            "filename": f.name,
            "path": str(f),  # Full path for local assets
            "brand": brand,
            "tags": inferred_tags,
            "source": f"local:{f.parent.name}",
            "notes": f"{size_mb:.1f}MB · {suffix[1:].upper()}",
        }
        entries.append(entry)

    return entries


def scan_local_tg_downloads() -> dict[str, list[dict]]:
    """Scan typical TG download locations.

    Returns:
      Dict mapping brand → list of reference entries
    """
    results = {brand: [] for brand in ["kilroy", "motion", "spong"]}

    # Known locations
    locations = [
        (Path(r"C:\Users\vince\Downloads"), "any"),
        (Path(r"C:\Users\vince\WAGMI\memegine-inbox\drive-folder"), "any"),
        (Path(r"C:\Users\vince\WAGMI\memegine\data\local_tg_media"), "any"),
    ]

    for folder, brand_hint in locations:
        if not folder.exists():
            continue

        # Scan subdirs — if one is named after a brand, use it
        for subdir in folder.iterdir():
            if not subdir.is_dir():
                continue

            name_lower = subdir.name.lower()
            target_brand = None

            if 'kilroy' in name_lower:
                target_brand = 'kilroy'
            elif 'motion' in name_lower:
                target_brand = 'motion'
            elif 'spong' in name_lower:
                target_brand = 'spong'

            if not target_brand:
                continue

            entries = scan_folder(subdir, target_brand)
            results[target_brand].extend(entries)

    return results


if __name__ == "__main__":
    # Quick test
    found = scan_local_tg_downloads()
    for brand, entries in found.items():
        if entries:
            print(f"{brand}: {len(entries)} items")
            for e in entries[:2]:
                print(f"  • {e['id'][:8]} — {e['filename']} ({e['notes']})")
