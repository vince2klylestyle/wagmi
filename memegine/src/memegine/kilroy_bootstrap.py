"""Bootstrap Kilroy reference index from image files in the directory.

One-shot script to scan data/projects/kilroy/references/ for image files
and build index.json with semantic tags.

Usage:
    python -c "from memegine.kilroy_bootstrap import bootstrap; bootstrap()"
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def bootstrap() -> int:
    """Scan kilroy references and build index.json. Return count of indexed images."""
    from .config import PROJECTS_ROOT

    refs_dir = PROJECTS_ROOT / "kilroy" / "references"
    index_path = refs_dir / "index.json"

    if not refs_dir.exists():
        print(f"[kilroy_bootstrap] Directory not found: {refs_dir}")
        return 0

    # Find all image files
    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    image_files = [
        f for f in refs_dir.iterdir()
        if f.is_file() and f.suffix.lower() in image_exts
    ]

    if not image_files:
        print(f"[kilroy_bootstrap] No images found in {refs_dir}")
        return 0

    # Build entries
    entries = []
    now = datetime.now().isoformat()

    for f in sorted(image_files):
        ref_id = f.stem  # use filename stem as ID
        entries.append({
            "id": ref_id,
            "filename": f.name,
            "added_at": now,
            "tags": ["kilroy", "graffiti", "art"],
            "source": "local",
            "notes": "",
        })

    # Write index
    try:
        index_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        print(f"[kilroy_bootstrap] Indexed {len(entries)} kilroy refs to {index_path}")
        return len(entries)
    except Exception as e:
        print(f"[kilroy_bootstrap] Error writing index: {e}")
        return 0


if __name__ == "__main__":
    count = bootstrap()
    print(f"Done: {count} images indexed")
