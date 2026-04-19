"""Video metadata — extract duration / fps / resolution from a video file.

Runs ffprobe to read the container metadata. Used by corpus ingest to
surface insights like "editors average 6-second cuts" or "this archive
is overwhelmingly 9:16 vertical 30fps".
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoMeta:
    path: str
    duration_sec: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    codec: str = ""
    audio: bool = False
    size_bytes: int = 0

    @property
    def aspect_ratio(self) -> str:
        if not self.width or not self.height:
            return "?"
        # Common ratio names for operator-friendly display.
        ratio = self.width / self.height
        if abs(ratio - 9 / 16) < 0.02:
            return "9:16"
        if abs(ratio - 1) < 0.02:
            return "1:1"
        if abs(ratio - 4 / 5) < 0.02:
            return "4:5"
        if abs(ratio - 16 / 9) < 0.02:
            return "16:9"
        if abs(ratio - 21 / 9) < 0.02:
            return "21:9"
        return f"{self.width}:{self.height}"


def _ffprobe() -> str:
    binary = shutil.which("ffprobe")
    if not binary:
        raise RuntimeError("ffprobe not found on PATH")
    return binary


def probe(video_path: Path | str) -> VideoMeta:
    """Return VideoMeta for a single video file."""
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    result = subprocess.run(
        [
            _ffprobe(), "-v", "error",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(video_path),
        ],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)

    meta = VideoMeta(
        path=str(video_path),
        size_bytes=video_path.stat().st_size,
    )

    # Duration lives on 'format'.
    fmt = data.get("format", {}) or {}
    try:
        meta.duration_sec = float(fmt.get("duration", 0))
    except (TypeError, ValueError):
        meta.duration_sec = 0.0

    # Streams: take the first video + detect audio presence.
    for stream in data.get("streams", []) or []:
        kind = stream.get("codec_type")
        if kind == "video" and not meta.width:
            meta.width = int(stream.get("width", 0))
            meta.height = int(stream.get("height", 0))
            meta.codec = stream.get("codec_name", "")
            # avg_frame_rate is a "num/den" string like "30000/1001".
            fps_raw = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/1"
            try:
                num, den = fps_raw.split("/")
                den_f = float(den)
                meta.fps = float(num) / den_f if den_f else 0.0
            except Exception:
                meta.fps = 0.0
        elif kind == "audio":
            meta.audio = True

    return meta


@dataclass
class CorpusVideoInsights:
    count: int = 0
    total_duration_sec: float = 0.0
    avg_duration_sec: float = 0.0
    median_duration_sec: float = 0.0
    aspect_counts: dict[str, int] = None
    fps_counts: dict[str, int] = None

    def as_text(self) -> str:
        lines = [
            f"=== video insights — {self.count} videos ===",
            f"  total duration:   {self.total_duration_sec:.1f}s "
            f"({self.total_duration_sec/60:.1f} min)",
            f"  avg duration:     {self.avg_duration_sec:.1f}s",
            f"  median duration:  {self.median_duration_sec:.1f}s",
        ]
        if self.aspect_counts:
            top = sorted(self.aspect_counts.items(), key=lambda x: -x[1])[:5]
            lines.append("  aspect ratios: " + ", ".join(f"{k}×{v}" for k, v in top))
        if self.fps_counts:
            top = sorted(self.fps_counts.items(), key=lambda x: -x[1])[:5]
            lines.append("  fps: " + ", ".join(f"{k}×{v}" for k, v in top))
        return "\n".join(lines)


def analyze_folder(folder: Path | str) -> CorpusVideoInsights:
    """Walk a folder, probe every video, return aggregated insights."""
    from .corpus import VIDEO_EXTS
    folder = Path(folder)
    metas: list[VideoMeta] = []
    for path in folder.rglob("*"):
        if path.is_file() and path.suffix.lower() in VIDEO_EXTS:
            try:
                metas.append(probe(path))
            except Exception:
                continue

    insight = CorpusVideoInsights(count=len(metas))
    if not metas:
        insight.aspect_counts = {}
        insight.fps_counts = {}
        return insight

    durations = sorted(m.duration_sec for m in metas if m.duration_sec > 0)
    insight.total_duration_sec = sum(durations)
    insight.avg_duration_sec = insight.total_duration_sec / len(durations) if durations else 0
    insight.median_duration_sec = durations[len(durations) // 2] if durations else 0

    aspect_counts: dict[str, int] = {}
    fps_counts: dict[str, int] = {}
    for m in metas:
        aspect_counts[m.aspect_ratio] = aspect_counts.get(m.aspect_ratio, 0) + 1
        # Bucket fps to the nearest whole frame-rate for readability.
        fps_key = f"{round(m.fps)}fps" if m.fps else "unknown"
        fps_counts[fps_key] = fps_counts.get(fps_key, 0) + 1
    insight.aspect_counts = aspect_counts
    insight.fps_counts = fps_counts
    return insight
