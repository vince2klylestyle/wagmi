"""
Health monitoring: heartbeat tracking and stall detection.

Writes periodic heartbeats to data/heartbeat.json so external monitors
can detect when the bot's main loop has stalled (not just when it crashes).

Usage:
    monitor = HealthMonitor()
    monitor.record_heartbeat(loop_duration_s=2.5, positions=3)
    status = monitor.get_status()
    if status["stalled"]:
        alert("Bot stalled!")
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any

logger = logging.getLogger("bot.monitoring.health")

_HEARTBEAT_FILE = os.path.join("data", "heartbeat.json")
_STALL_THRESHOLD_S = 600  # 10 minutes without heartbeat = stalled

# Single module-level lock shared by EVERY writer of data/heartbeat.json
# (HealthMonitor.record_heartbeat, the heartbeat daemon, auto_recovery.save_heartbeat,
# the main-loop error handler, and graceful shutdown). The bot now writes the
# heartbeat from both the parallel scan loop AND a 30s daemon thread, so without a
# shared lock + atomic replace the file can tear/corrupt mid-read for watchdog.py.
HEARTBEAT_LOCK = threading.Lock()


def write_heartbeat_atomic(data: Dict[str, Any], filepath: str = _HEARTBEAT_FILE) -> None:
    """Atomically write the heartbeat JSON.

    Guarantees:
      1. The output ALWAYS carries a fresh 'last_alive' ISO-8601 timestamp in the
         exact key+format watchdog.py:heartbeat_age_seconds() reads, plus 'pid'
         (preserving the live save_heartbeat() contract). Any caller-supplied
         'last_alive'/'pid' are respected; otherwise they are filled in here so no
         write can ever omit the watchdog's staleness key.
      2. The write is ATOMIC: serialize to a temp file in the same dir, fsync, then
         os.replace() onto the target — a reader never sees a partial/truncated file.
      3. All writers serialize on HEARTBEAT_LOCK so concurrent daemon + main-loop
         writes cannot interleave/tear.
    """
    payload = dict(data)
    payload.setdefault("last_alive", datetime.now(timezone.utc).isoformat())
    payload.setdefault("pid", os.getpid())

    directory = os.path.dirname(filepath) or "."
    with HEARTBEAT_LOCK:
        os.makedirs(directory, exist_ok=True)
        tmp = f"{filepath}.{os.getpid()}.{threading.get_ident()}.tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(payload, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            # os.replace is atomic on POSIX and Windows. On Windows the replace
            # can transiently fail with PermissionError if a reader (watchdog.py)
            # has the target briefly open; retry a few times so the heartbeat is
            # never skipped, then fall back so we don't leave a stale file.
            for attempt in range(5):
                try:
                    os.replace(tmp, filepath)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.02)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass


class HealthMonitor:
    """Tracks bot health via periodic heartbeats."""

    def __init__(self, heartbeat_file: str = _HEARTBEAT_FILE, stall_threshold_s: int = _STALL_THRESHOLD_S):
        self._file = heartbeat_file
        self._stall_threshold = stall_threshold_s
        self._last_heartbeat = time.time()
        self._loop_durations: list = []  # Last 20 loop durations
        self._scan_count = 0
        self._error_count = 0
        self._start_time = time.time()

    def record_heartbeat(
        self,
        loop_duration_s: float = 0.0,
        positions: int = 0,
        equity: float = 0.0,
        extra: Dict[str, Any] = None,
    ):
        """Record a heartbeat from the main trading loop."""
        self._last_heartbeat = time.time()
        self._scan_count += 1

        if loop_duration_s > 0:
            self._loop_durations.append(loop_duration_s)
            if len(self._loop_durations) > 20:
                self._loop_durations = self._loop_durations[-20:]

        _now_iso = datetime.now(timezone.utc).isoformat()
        heartbeat = {
            # 'last_alive' is the key + ISO-8601 format watchdog.py reads to compute
            # staleness; it MUST be present on every write or the watchdog treats the
            # heartbeat as missing and false-positives a stall.
            "last_alive": _now_iso,
            "pid": os.getpid(),
            "timestamp": _now_iso,
            "epoch": self._last_heartbeat,
            "uptime_s": round(self._last_heartbeat - self._start_time, 0),
            "scan_count": self._scan_count,
            "loop_duration_s": round(loop_duration_s, 2),
            "avg_loop_s": round(
                sum(self._loop_durations) / len(self._loop_durations), 2
            ) if self._loop_durations else 0,
            "positions": positions,
            "equity": round(equity, 2),
            "errors": self._error_count,
        }
        if extra:
            heartbeat.update(extra)

        try:
            write_heartbeat_atomic(heartbeat, self._file)
        except Exception as e:
            logger.warning(f"Failed to write heartbeat: {e}")

    def record_error(self):
        """Record an error occurrence."""
        self._error_count += 1

    def get_status(self) -> Dict[str, Any]:
        """Get current health status."""
        now = time.time()
        since_last = now - self._last_heartbeat
        return {
            "last_heartbeat_s_ago": round(since_last, 1),
            "stalled": since_last > self._stall_threshold,
            "uptime_s": round(now - self._start_time, 0),
            "scan_count": self._scan_count,
            "error_count": self._error_count,
            "avg_loop_s": round(
                sum(self._loop_durations) / len(self._loop_durations), 2
            ) if self._loop_durations else 0,
        }

    def is_healthy(self) -> bool:
        """Quick health check."""
        return not self.get_status()["stalled"]
