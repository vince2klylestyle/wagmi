"""Video frame extraction — break videos into sampled stills.

Uses ffmpeg (already a hard dependency of the editor / grading / music
modules). Extracts N evenly-spaced frames from a video for corpus
ingest and manual ref review.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def _ffmpeg() -> str:
    binary = shutil.which("ffmpeg")
    if not binary:
        raise RuntimeError("ffmpeg not found on PATH")
    return binary


def _ffprobe() -> str:
    binary = shutil.which("ffprobe")
    if not binary:
        raise RuntimeError("ffprobe not found on PATH")
    return binary


def duration_seconds(video_path: Path) -> float:
    """Return the video duration in seconds."""
    result = subprocess.run(
        [
            _ffprobe(), "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video_path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def extract(
    video_path: Path | str,
    *,
    n_frames: int = 5,
    output_dir: Path | None = None,
    skip_first_seconds: float = 0.5,
    skip_last_seconds: float = 0.5,
) -> list[Path]:
    """Extract `n_frames` evenly-spaced stills from the video.

    Skips the first/last half-second by default (intros/outros often
    fade in/out and look nothing like the piece).

    Returns paths to the extracted frame files. Output is tempfiles
    unless `output_dir` is given.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if n_frames < 1:
        raise ValueError("n_frames must be >= 1")

    duration = duration_seconds(video_path)
    if duration <= skip_first_seconds + skip_last_seconds:
        skip_first_seconds = 0
        skip_last_seconds = 0

    usable = max(0.0, duration - skip_first_seconds - skip_last_seconds)
    if n_frames == 1:
        times = [skip_first_seconds + usable / 2]
    else:
        step = usable / (n_frames - 1) if n_frames > 1 else 0
        times = [skip_first_seconds + i * step for i in range(n_frames)]

    out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="memegine-frames-"))
    out_dir.mkdir(parents=True, exist_ok=True)

    frame_paths: list[Path] = []
    for i, t in enumerate(times):
        dest = out_dir / f"{video_path.stem}_frame_{i+1:03d}.jpg"
        # -ss before -i is fast seek; -frames:v 1 means one frame only;
        # -q:v 2 is high JPEG quality.
        subprocess.run(
            [
                _ffmpeg(), "-y",
                "-ss", f"{t:.3f}",
                "-i", str(video_path),
                "-frames:v", "1",
                "-q:v", "2",
                str(dest),
            ],
            capture_output=True, check=True,
        )
        if dest.exists():
            frame_paths.append(dest)
    return frame_paths
