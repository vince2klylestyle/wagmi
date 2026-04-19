"""Combined serve — start bot and scheduler in one process.

For the operator who wants one command, one tmux pane, one tail. The
scheduler runs on a background thread; the bot polls in the main thread.
A SIGINT stops both cleanly.

Requires python-telegram-bot. If Telegram isn't configured the serve
refuses to start (use `memegine schedule run` for scheduler-only).
"""
from __future__ import annotations

import signal
import threading
from dataclasses import dataclass

from . import scheduler, telegram_bot


@dataclass
class ServeOptions:
    poll_seconds: int = 30
    telegram_notify: bool = True
    scheduler_only: bool = False


class _SchedulerThread(threading.Thread):
    def __init__(self, cfg: telegram_bot.BotConfig, poll: int):
        super().__init__(daemon=True, name="memegine-scheduler")
        self._cfg = cfg
        self._poll = poll
        self._stop = threading.Event()

    def run(self) -> None:
        deliver = None
        if self._cfg.token and self._cfg.chat_id_for_scheduler:
            deliver = lambda job, result: telegram_bot.send_scheduler_result(
                self._cfg, job, result,
            )
        # Soft loop — we can't interrupt sleep cleanly without reworking
        # scheduler.run_loop. As a compromise, we run with a smaller poll
        # and check the stop event between iterations via stop_after=None.
        # For a more graceful exit, operator sends SIGINT.
        while not self._stop.is_set():
            # Run N iterations at a time so we can check _stop periodically.
            scheduler.run_loop(
                poll_seconds=self._poll, deliver=deliver, stop_after=1,
            )

    def stop(self) -> None:
        self._stop.set()


def run(options: ServeOptions | None = None) -> None:
    options = options or ServeOptions()
    cfg = telegram_bot.BotConfig.from_env()

    if not options.scheduler_only:
        if not cfg.token or not cfg.allowed_user_ids:
            raise telegram_bot.BotConfigError(
                "telegram env missing — set MEMEGINE_TELEGRAM_BOT_TOKEN and "
                "MEMEGINE_TELEGRAM_ALLOWED_USER_IDS, or run with scheduler_only=True"
            )

    sched_thread = _SchedulerThread(cfg, options.poll_seconds)
    sched_thread.start()
    print(f"[memegine] scheduler thread started (poll={options.poll_seconds}s)")

    def _shutdown(signum, frame):
        print("\n[memegine] shutdown requested — stopping scheduler")
        sched_thread.stop()

    try:
        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)
    except (ValueError, AttributeError):
        # Not all platforms / Jupyter contexts support signal handlers.
        pass

    if options.scheduler_only:
        print("[memegine] scheduler-only mode — no bot started")
        sched_thread.join()
        return

    print(f"[memegine] bot starting (allowlist size={len(cfg.allowed_user_ids)})")
    try:
        telegram_bot.run_bot(cfg)
    finally:
        sched_thread.stop()
        sched_thread.join(timeout=5)
        print("[memegine] exited")
