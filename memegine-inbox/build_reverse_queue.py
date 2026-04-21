"""Build a work queue for local reverse: one representative frame per
source video, plus the file path for Claude to Read."""
from __future__ import annotations

import json
from pathlib import Path

from memegine import reference_lib
from memegine.config import settings


def main():
    refs = reference_lib._load_index()
    # Group by video tag.
    by_video: dict[str, list[dict]] = {}
    for r in refs:
        video_tag = next(
            (t for t in r.get("tags", []) or [] if t.startswith("video:")),
            None,
        )
        if video_tag is None:
            continue
        by_video.setdefault(video_tag, []).append(r)

    queue = []
    for video_tag, members in sorted(by_video.items()):
        # Pick the middle frame (frame:3 by preference, else middle of list).
        chosen = next(
            (r for r in members if "frame:3" in (r.get("tags") or [])),
            members[len(members) // 2] if members else None,
        )
        if chosen is None:
            continue
        path = settings.references_dir / chosen["filename"]
        queue.append({
            "video": video_tag.replace("video:", ""),
            "ref_id": chosen["id"],
            "path": str(path),
            "sibling_count": len(members),
        })

    out = Path(r"C:\Users\vince\WAGMI\memegine-inbox\reverse_queue.json")
    out.write_text(json.dumps(queue, indent=2), encoding="utf-8")
    print(f"queue: {len(queue)} videos, written to {out}")
    for entry in queue[:5]:
        print(f"  {entry['ref_id']}  {entry['video'][:40]}  {entry['path']}")


if __name__ == "__main__":
    main()
