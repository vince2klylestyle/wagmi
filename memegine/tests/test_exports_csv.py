from __future__ import annotations

import csv
import datetime as dt
import json

import pytest

from memegine import exports_csv


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    from memegine import reference_lib, performance
    from memegine.config import settings
    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs", raising=False)
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(settings, "references_dir", tmp_path / "refs", raising=False)
    (tmp_path / "refs").mkdir()
    monkeypatch.setattr(performance, "_store_path", lambda: tmp_path / "perf.jsonl")
    yield tmp_path


def test_export_archive_writes_rows(isolated):
    logs = isolated / "logs"
    today = dt.datetime.utcnow().date().isoformat()
    rec = {
        "id": "b1", "created_at": f"{today}T00:10:00Z",
        "kind": "prompt", "format": "photoreal_portrait",
        "intent": "a trader", "system": "SYS", "user": "USR",
    }
    (logs / f"briefs-{today}.jsonl").write_text(json.dumps(rec) + "\n")

    dst = isolated / "archive.csv"
    count = exports_csv.export_archive(dst)
    assert count == 1
    rows = list(csv.DictReader(dst.open(encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["kind"] == "prompt"
    assert rows[0]["format"] == "photoreal_portrait"


def test_export_refs_writes_rows(isolated):
    from memegine import reference_lib
    img = isolated / "x.png"
    img.write_bytes(b"PNG")
    reference_lib.add(img, tags=["night"])
    img2 = isolated / "y.png"
    img2.write_bytes(b"PNG2")
    reference_lib.add(img2, prompt="win", winner=True)

    dst = isolated / "refs.csv"
    count = exports_csv.export_refs(dst)
    assert count == 2
    rows = list(csv.DictReader(dst.open(encoding="utf-8")))
    winners = [r for r in rows if r["is_winner"] == "True"]
    assert len(winners) == 1


def test_export_performance_dedupes_by_bundle(isolated):
    from memegine import performance
    performance.log(post_bundle_id="b1", likes=100, window="24h")
    performance.log(post_bundle_id="b1", likes=500, window="7d")
    performance.log(post_bundle_id="b2", likes=50)

    dst = isolated / "perf.csv"
    count = exports_csv.export_performance(dst)
    # b1 dedupes to latest entry (7d), so 2 total.
    assert count == 2
    rows = list(csv.DictReader(dst.open(encoding="utf-8")))
    bids = {r["post_bundle_id"] for r in rows}
    assert bids == {"b1", "b2"}


def test_export_empty_stores(isolated):
    dst = isolated / "refs.csv"
    count = exports_csv.export_refs(dst)
    assert count == 0
    # Header row still written.
    assert dst.exists()
    rows = dst.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1  # header only
