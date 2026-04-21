"""Download every file in the Drive folder listing, one at a time.

Gdown stops the whole batch on one failure. This iterates file-by-file
so a single locked/rate-limited file doesn't block the rest.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import gdown


LOG = Path(r"C:\Users\vince\WAGMI\memegine-inbox\gdown.log")
DEST = Path(r"C:\Users\vince\WAGMI\memegine-inbox\drive-folder\MOTION")
DEST.mkdir(parents=True, exist_ok=True)


def parse_entries(log_path: Path) -> list[tuple[str, str]]:
    """Extract (file_id, filename) tuples from gdown's 'Processing file' lines."""
    pat = re.compile(r"^Processing file (\S+) (.+)$")
    entries = []
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = pat.match(line.strip())
        if m:
            entries.append((m.group(1), m.group(2).strip()))
    # De-dupe by file_id, preserve order.
    seen = set()
    unique = []
    for fid, name in entries:
        if fid not in seen:
            seen.add(fid)
            unique.append((fid, name))
    return unique


def main():
    entries = parse_entries(LOG)
    print(f"total entries: {len(entries)}")

    ok = 0
    skipped = 0
    failed = []
    for fid, name in entries:
        dst = DEST / name
        if dst.exists() and dst.stat().st_size > 0:
            skipped += 1
            continue
        url = f"https://drive.google.com/uc?id={fid}"
        try:
            gdown.download(url, str(dst), quiet=True)
            ok += 1
            print(f"  [ok ] {name}")
        except Exception as exc:
            failed.append((fid, name, str(exc)))
            print(f"  [err] {name}  ({type(exc).__name__})")
    print()
    print(f"done. ok={ok} skipped={skipped} failed={len(failed)}")
    for fid, name, why in failed[:20]:
        print(f"  fail: {name}  ({why[:80]})")


if __name__ == "__main__":
    main()
