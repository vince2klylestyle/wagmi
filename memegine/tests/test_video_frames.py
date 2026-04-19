from __future__ import annotations

import shutil

import pytest

from memegine import video_frames

ffmpeg_available = shutil.which("ffmpeg") and shutil.which("ffprobe")
pytestmark = pytest.mark.skipif(not ffmpeg_available, reason="ffmpeg not installed")


def _make_tiny_video(dst, seconds: float = 2.0) -> None:
    import subprocess
    # Generate a 2-second color-pattern video via ffmpeg's lavfi.
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=128x128:rate=24",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            str(dst),
        ],
        capture_output=True, check=True,
    )


def test_extract_produces_n_frames(tmp_path):
    vid = tmp_path / "test.mp4"
    _make_tiny_video(vid)
    frames = video_frames.extract(vid, n_frames=3, output_dir=tmp_path / "out")
    assert len(frames) == 3
    for f in frames:
        assert f.exists()
        assert f.stat().st_size > 0


def test_extract_single_frame(tmp_path):
    vid = tmp_path / "test.mp4"
    _make_tiny_video(vid, seconds=2.0)
    frames = video_frames.extract(vid, n_frames=1, output_dir=tmp_path / "out")
    assert len(frames) == 1


def test_extract_rejects_missing_video(tmp_path):
    with pytest.raises(FileNotFoundError):
        video_frames.extract(tmp_path / "nope.mp4", n_frames=3)


def test_extract_rejects_bad_n(tmp_path):
    vid = tmp_path / "test.mp4"
    _make_tiny_video(vid)
    with pytest.raises(ValueError):
        video_frames.extract(vid, n_frames=0)


def test_duration_returns_positive(tmp_path):
    vid = tmp_path / "test.mp4"
    _make_tiny_video(vid, seconds=2.0)
    d = video_frames.duration_seconds(vid)
    assert 1.5 < d < 2.5
