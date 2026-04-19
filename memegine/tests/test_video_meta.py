from __future__ import annotations

import shutil

import pytest

from memegine import video_meta

ffmpeg_available = shutil.which("ffmpeg") and shutil.which("ffprobe")
pytestmark = pytest.mark.skipif(not ffmpeg_available, reason="ffmpeg not installed")


def _make_video(dst, *, seconds=2.0, size="128x128", fps=30):
    import subprocess
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size={size}:rate={fps}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            str(dst),
        ],
        capture_output=True, check=True,
    )


def test_probe_returns_metadata(tmp_path):
    vid = tmp_path / "a.mp4"
    _make_video(vid, seconds=2.0, size="160x120", fps=30)
    meta = video_meta.probe(vid)
    assert 1.5 < meta.duration_sec < 2.5
    assert meta.width == 160
    assert meta.height == 120
    assert round(meta.fps) == 30


def test_aspect_ratio_classified(tmp_path):
    vid = tmp_path / "sq.mp4"
    _make_video(vid, size="100x100")
    assert video_meta.probe(vid).aspect_ratio == "1:1"

    vid2 = tmp_path / "ls.mp4"
    _make_video(vid2, size="320x180")
    assert video_meta.probe(vid2).aspect_ratio == "16:9"


def test_analyze_folder_aggregates(tmp_path):
    _make_video(tmp_path / "a.mp4", seconds=1.0)
    _make_video(tmp_path / "b.mp4", seconds=2.0)
    _make_video(tmp_path / "c.mp4", seconds=3.0)
    insights = video_meta.analyze_folder(tmp_path)
    assert insights.count == 3
    assert 5.5 < insights.total_duration_sec < 6.5
    assert 1.5 < insights.avg_duration_sec < 2.5


def test_analyze_empty_folder(tmp_path):
    insights = video_meta.analyze_folder(tmp_path)
    assert insights.count == 0
    assert insights.total_duration_sec == 0


def test_probe_raises_on_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        video_meta.probe(tmp_path / "nope.mp4")


def test_insights_text_formats_cleanly(tmp_path):
    _make_video(tmp_path / "a.mp4", seconds=1.0)
    insights = video_meta.analyze_folder(tmp_path)
    text = insights.as_text()
    assert "video insights" in text
    assert "total duration" in text
