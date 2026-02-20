"""
Telegram command bot for runtime control and monitoring.

Commands:
  /status       - Bot status, equity, positions
  /positions    - Open position details
  /ml           - ML learner stats
  /performance  - Rolling win rate and metrics
  /close <sym>  - Force close a symbol's position
  /closeall     - Force close all positions
  /pause        - Pause trading (signals still evaluated, no opens)
  /resume       - Resume trading
  /manual_positions - List manually-detected positions (not bot-managed)

Security: Only the configured Telegram user ID is allowed.
All commands logged to data/logs/telegram.csv.
"""

import csv
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("bot.alerts.telegram_bot")

_LOG_DIR = os.path.join("data", "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "telegram.csv")
_LOG_HEADERS = ["timestamp", "user_id", "command", "args"]


def _ensure_log():
    os.makedirs(_LOG_DIR, exist_ok=True)
    if not os.path.exists(_LOG_FILE):
        with open(_LOG_FILE, "w", newline="") as f:
            csv.writer(f).writerow(_LOG_HEADERS)


def _log_command(user_id: int, command: str, args: str = ""):
    _ensure_log()
    try:
        with open(_LOG_FILE, "a", newline="") as f:
            csv.writer(f).writerow([
                datetime.now(timezone.utc).isoformat(),
                str(user_id), command, args,
            ])
    except Exception:
        pass


class TelegramCommandBot:
    """
    Polls Telegram for commands and dispatches to bot runtime.

    Uses simple getUpdates polling (no webhook server needed).
    Hooks into the MultiStrategyBot instance for live state access.
    """

    def __init__(
        self,
        token: str,
        allowed_user_id: int,
        bot_instance=None,
    ):
        self.token = token
        self.allowed_user_id = allowed_user_id
        self.bot = bot_instance
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._offset = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._paused = False

        if not token:
            logger.info("Telegram bot: no token configured, commands disabled")

    @property
    def is_paused(self) -> bool:
        return self._paused

    def start(self):
        """Start polling in a background thread."""
        if not self.token:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Telegram command bot started")

    def stop(self):
        self._running = False

    def _poll_loop(self):
        import requests
        while self._running:
            try:
                resp = requests.get(
                    f"{self._base_url}/getUpdates",
                    params={"offset": self._offset, "timeout": 10},
                    timeout=15,
                )
                if resp.status_code != 200:
                    time.sleep(5)
                    continue

                data = resp.json()
                for update in data.get("result", []):
                    self._offset = update["update_id"] + 1
                    msg = update.get("message", {})
                    self._handle_message(msg)

            except Exception as e:
                logger.debug(f"Telegram poll error: {e}")
                time.sleep(5)

    def _handle_message(self, msg: dict):
        import requests
        chat_id = msg.get("chat", {}).get("id")
        user_id = msg.get("from", {}).get("id")
        text = (msg.get("text") or "").strip()

        if not text or not chat_id:
            return

        # Security: only allow configured user
        if user_id != self.allowed_user_id:
            logger.warning(f"Unauthorized Telegram command from user {user_id}")
            return

        parts = text.split()
        command = parts[0].lower().split("@")[0]  # strip bot mention
        args = " ".join(parts[1:])

        _log_command(user_id, command, args)

        response = self._dispatch(command, args)
        if response:
            try:
                requests.post(
                    f"{self._base_url}/sendMessage",
                    json={"chat_id": chat_id, "text": response, "parse_mode": "Markdown"},
                    timeout=10,
                )
            except Exception as e:
                logger.warning(f"Failed to send Telegram reply: {e}")

    def _dispatch(self, command: str, args: str) -> str:
        handlers = {
            "/status": self._cmd_status,
            "/positions": self._cmd_positions,
            "/ml": self._cmd_ml,
            "/performance": self._cmd_performance,
            "/close": lambda: self._cmd_close(args),
            "/closeall": self._cmd_closeall,
            "/pause": self._cmd_pause,
            "/resume": self._cmd_resume,
        }
        handler = handlers.get(command)
        if handler:
            try:
                return handler()
            except Exception as e:
                return f"Error: {e}"
        return ""

    def _cmd_status(self) -> str:
        if not self.bot:
            return "Bot not connected"
        eq = self.bot.risk_mgr.equity
        n_pos = self.bot.pos_mgr.get_open_count()
        daily = self.bot.risk_mgr.circuit_breaker.daily_pnl
        paused = "PAUSED" if self._paused else "ACTIVE"
        return (
            f"*Status: {paused}*\n"
            f"Equity: ${eq:,.2f}\n"
            f"Open positions: {n_pos}\n"
            f"Daily PnL: ${daily:+,.2f}\n"
            f"Tick: {self.bot._tick}"
        )

    def _cmd_positions(self) -> str:
        if not self.bot:
            return "Bot not connected"
        from data.fetcher import DataFetcher
        from trading_config import DEFAULT_SYMBOLS
        open_pos = self.bot.pos_mgr.get_open_positions()
        if not open_pos:
            return "No open positions"
        lines = []
        for sym, pos in open_pos.items():
            price = self.bot.fetcher.latest_price(sym, DEFAULT_SYMBOLS.get(sym, type('', (), {'coingecko_id': sym.lower()})()).coingecko_id) or 0
            pnl = (price - pos.entry) * pos.qty * pos.leverage if pos.side == "LONG" else (pos.entry - price) * pos.qty * pos.leverage
            lines.append(
                f"*{sym}* {pos.side} {pos.leverage:.0f}x\n"
                f"  Entry: {pos.entry} | State: {pos.state}\n"
                f"  SL: {pos.sl} | TP1: {pos.tp1} | TP2: {pos.tp2}\n"
                f"  Unrealized: ${pnl:+,.2f} | Realized: ${pos.realized_pnl:+,.2f}"
            )
        return "\n\n".join(lines)

    def _cmd_ml(self) -> str:
        if not self.bot or not self.bot.ml:
            return "ML disabled"
        ml = self.bot.ml
        return (
            f"*ML Learner*\n"
            f"Trade outcomes: {len(ml.outcomes)}\n"
            f"Snapshots: {len(ml.snapshots)}\n"
            f"Trade model: {'trained' if ml.weights else 'waiting'}\n"
            f"Snapshot model: {'trained' if ml.snapshot_weights else 'waiting'}\n"
            f"Fast model: {'trained' if ml.fast_weights else 'waiting'}"
        )

    def _cmd_performance(self) -> str:
        from data.learning import get_performance
        perf = get_performance()
        if not perf:
            return "No performance data yet"
        return (
            f"*Performance*\n"
            f"Trades: {perf.get('total_trades', 0)}\n"
            f"WR (20): {perf.get('win_rate_20', 0):.0%}\n"
            f"WR (50): {perf.get('win_rate_50', 0):.0%}\n"
            f"Avg R:R: {perf.get('avg_rr', 0):.2f}\n"
            f"TP1 rate: {perf.get('tp1_success_rate', 0):.0%}\n"
            f"TP1→SL: {perf.get('tp1_to_sl_rate', 0):.0%}\n"
            f"Total PnL: ${perf.get('total_pnl', 0):+,.2f}"
        )

    def _cmd_close(self, args: str) -> str:
        if not self.bot:
            return "Bot not connected"
        symbol = args.strip().upper()
        if not symbol:
            return "Usage: /close SYMBOL"
        from trading_config import DEFAULT_SYMBOLS
        price = self.bot.fetcher.latest_price(
            symbol, DEFAULT_SYMBOLS.get(symbol, type('', (), {'coingecko_id': symbol.lower()})()).coingecko_id
        )
        if not price:
            return f"Cannot get price for {symbol}"
        event = self.bot.pos_mgr.force_close(symbol, price, "TELEGRAM_CLOSE")
        if event:
            return f"Closed {symbol} @ {price} | PnL: ${event.pnl:+,.2f}"
        return f"No open position for {symbol}"

    def _cmd_closeall(self) -> str:
        if not self.bot:
            return "Bot not connected"
        from trading_config import DEFAULT_SYMBOLS
        closed = []
        for sym in list(self.bot.pos_mgr.get_open_positions().keys()):
            price = self.bot.fetcher.latest_price(
                sym, DEFAULT_SYMBOLS.get(sym, type('', (), {'coingecko_id': sym.lower()})()).coingecko_id
            )
            if price:
                event = self.bot.pos_mgr.force_close(sym, price, "TELEGRAM_CLOSE")
                if event:
                    closed.append(f"{sym}: ${event.pnl:+,.2f}")
        if closed:
            return "Closed:\n" + "\n".join(closed)
        return "No positions to close"

    def _cmd_pause(self) -> str:
        self._paused = True
        return "Trading PAUSED. Signals still evaluated but no new positions will open."

    def _cmd_resume(self) -> str:
        self._paused = False
        return "Trading RESUMED."
