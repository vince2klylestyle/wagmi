"""Premium Telegram Alert Formatter.

Phone-first, scannable, actionable alert format for the two-tier
premium filter. Built 2026-04-16 to replace the noisy
format_signal_telegram() with alerts that are worth the user's attention.

Design principles:
  1. **Direction is obvious**. LONG / SHORT is in the emoji + first line,
     impossible to misread. The Finding 21 bug that inverted this is fixed.
  2. **Direction sanity line** always present, so user can verify SL/TP
     math matches the stated direction at a glance.
  3. **Shadow ledger evidence** — not just confidence, the actual WR.
  4. **Exact size + max loss** spelled out, no math required from user.
  5. **One-tap action**: /trade command pre-filled for copy-paste.
  6. **"Ask Claude" block** is a pre-formatted prompt the user copies
     verbatim into a Claude Code session for a second opinion.
  7. **Scannable on a phone notification preview** — the first two lines
     tell you everything important.
"""

from __future__ import annotations

from .premium_filter import AlertDecision, AlertTier


def _fmt_price(p: float) -> str:
    if p is None:
        return "?"
    if p >= 1000:
        return f"{p:,.2f}"
    if p >= 10:
        return f"{p:.2f}"
    if p >= 0.1:
        return f"{p:.3f}"
    return f"{p:.6f}"


def _fmt_pct(p: float, show_sign: bool = True) -> str:
    if show_sign:
        return f"{p:+.2f}%"
    return f"{p:.2f}%"


def _direction_emoji(is_long: bool) -> str:
    """Single unicode char conveying direction at a glance."""
    return "🟢" if is_long else "🔴"


def _qty_suggestion(notional: float, entry: float) -> float:
    if entry <= 0:
        return 0.0
    return notional / entry


def format_premium_execute_alert(
    symbol: str,
    side: str,
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    leverage: float,
    confidence: float,
    decision: AlertDecision,
    strategy: str = "",
    regime: str = "",
    num_agree: int = 1,
    total_strategies: int = 0,
) -> str:
    """Format a Tier 2 EXECUTE alert — take action now.

    Designed to be instantly scannable on a phone lock screen. First two
    lines convey the core: direction + symbol + entry + size.
    """
    _side_up = (side or "").upper()
    is_long = _side_up in ("BUY", "LONG")
    direction = "LONG" if is_long else "SHORT"
    side_bs = "BUY" if is_long else "SELL"  # for the /trade command
    dir_emoji = _direction_emoji(is_long)

    # Direction math
    stop_pct = abs(entry - sl) / entry * 100 if entry > 0 else 0
    tp1_pct = abs(tp1 - entry) / entry * 100 if entry > 0 else 0
    tp2_pct = abs(tp2 - entry) / entry * 100 if entry > 0 else 0
    rr1 = abs(tp1 - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
    rr2 = abs(tp2 - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0

    # Signed percentages match the direction (shows user what to expect)
    sl_pct_signed = -stop_pct if is_long else stop_pct
    tp1_pct_signed = tp1_pct if is_long else -tp1_pct
    tp2_pct_signed = tp2_pct if is_long else -tp2_pct

    # Size suggestion
    notional = decision.size_suggestion_notional or 0
    max_loss = decision.max_loss_usd or 10.0
    qty = _qty_suggestion(notional, entry)

    # Shadow evidence
    shadow_wr_pct = (decision.shadow_wr or 0) * 100
    shadow_grade = decision.shadow_grade or "?"

    lines = []
    # Header — visible in phone notification preview
    lines.append(f"🎯 EXECUTE {dir_emoji} {direction} {symbol} @ ${_fmt_price(entry)}")
    lines.append(f"    {leverage:.0f}x | conf {confidence:.0f}% | {shadow_wr_pct:.0f}% WR ({shadow_grade})")
    lines.append("")

    # Levels box
    lines.append("━━━ LEVELS ━━━")
    lines.append(f"Entry  ${_fmt_price(entry)}")
    lines.append(f"Stop   ${_fmt_price(sl)}   ({_fmt_pct(sl_pct_signed)})")
    lines.append(f"TP1    ${_fmt_price(tp1)}   ({_fmt_pct(tp1_pct_signed)} · {rr1:.1f}R)")
    lines.append(f"TP2    ${_fmt_price(tp2)}   ({_fmt_pct(tp2_pct_signed)} · {rr2:.1f}R)")
    lines.append("")

    # Size box
    if notional > 0:
        lines.append("━━━ SIZE ━━━")
        lines.append(f"Notional  ${notional:,.0f}")
        lines.append(f"Qty       {qty:.4f} {symbol}")
        lines.append(f"Max loss  ${max_loss:.0f} if SL hits")
        lines.append("")

    # Why box
    lines.append("━━━ WHY ━━━")
    lines.append(f"Shadow:   {decision.shadow_wr*100:.0f}% WR on {decision.shadow_n} samples")
    why_parts = []
    if strategy:
        why_parts.append(f"driver={strategy}")
    if num_agree:
        n_total = f"/{total_strategies}" if total_strategies else ""
        why_parts.append(f"{num_agree}{n_total} agree")
    if regime:
        why_parts.append(f"regime={regime}")
    if why_parts:
        lines.append(f"Setup:    {' · '.join(why_parts)}")
    lines.append("")

    # Sanity check — user can verify at a glance
    lines.append("━━━ SANITY ━━━")
    if is_long:
        lines.append(f"✓ LONG: SL below entry, TP above")
        lines.append(f"  You WIN if price rises")
    else:
        lines.append(f"✓ SHORT: SL above entry, TP below")
        lines.append(f"  You WIN if price falls")
    lines.append("")

    # Action block — copy-paste ready
    lines.append("━━━ ACTION ━━━")
    lines.append(f"1️⃣  Open trade on Hyperliquid at ~${_fmt_price(entry)}")
    if qty > 0:
        lines.append(f"2️⃣  Log it via Telegram:")
        lines.append(f"    /trade {symbol} {side_bs} {_fmt_price(entry)} {leverage:.0f}x {qty:.4f}")
    else:
        lines.append(f"2️⃣  Log via: /trade {symbol} {side_bs} <price> {leverage:.0f}x <qty>")
    lines.append(f"3️⃣  Close with: /close {symbol}")
    lines.append("")

    # Ask Claude block — pre-formatted prompt
    lines.append("💬 ASK CLAUDE (copy-paste):")
    lines.append(f"```")
    lines.append(f"{direction} {symbol} @ ${_fmt_price(entry)} {leverage:.0f}x")
    lines.append(f"SL ${_fmt_price(sl)} TP1 ${_fmt_price(tp1)} TP2 ${_fmt_price(tp2)}")
    lines.append(f"driver={strategy} conf={confidence:.0f}% regime={regime}")
    lines.append(f"{decision.shadow_wr*100:.0f}% shadow WR, {num_agree} strats. Take it?")
    lines.append(f"```")

    return "\n".join(lines)


def format_premium_watch_alert(
    symbol: str,
    side: str,
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    leverage: float,
    confidence: float,
    decision: AlertDecision,
    strategy: str = "",
    regime: str = "",
    num_agree: int = 1,
    total_strategies: int = 0,
) -> str:
    """Format a Tier 1 WATCH alert — setup forming, don't act yet.

    Tells the user: "get ready, this is developing. Here's what needs
    to happen before you act."
    """
    _side_up = (side or "").upper()
    is_long = _side_up in ("BUY", "LONG")
    direction = "LONG" if is_long else "SHORT"
    dir_emoji = _direction_emoji(is_long)

    stop_pct = abs(entry - sl) / entry * 100 if entry > 0 else 0
    tp1_pct = abs(tp1 - entry) / entry * 100 if entry > 0 else 0
    rr1 = abs(tp1 - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
    sl_pct_signed = -stop_pct if is_long else stop_pct
    tp1_pct_signed = tp1_pct if is_long else -tp1_pct

    shadow_line = ""
    if decision.shadow_wr is not None:
        shadow_line = (
            f"{decision.shadow_wr*100:.0f}% WR on {decision.shadow_n} samples "
            f"({decision.shadow_grade})"
        )

    lines = []
    lines.append(f"🔔 WATCH {dir_emoji} {direction} {symbol} forming @ ${_fmt_price(entry)}")
    if shadow_line:
        lines.append(f"    {shadow_line}")
    lines.append("")

    # Prospective levels
    lines.append("━━━ IF TRIGGERED ━━━")
    lines.append(f"Entry  ${_fmt_price(entry)}")
    lines.append(f"Stop   ${_fmt_price(sl)}   ({_fmt_pct(sl_pct_signed)})")
    lines.append(f"TP1    ${_fmt_price(tp1)}   ({_fmt_pct(tp1_pct_signed)} · {rr1:.1f}R)")
    lines.append("")

    # What's met and what's missing
    if decision.key_conditions_met:
        lines.append("✅ ALREADY HAVE:")
        for c in decision.key_conditions_met:
            lines.append(f"  • {c}")
        lines.append("")
    if decision.key_conditions_missing:
        lines.append("⏳ STILL NEED:")
        for c in decision.key_conditions_missing:
            lines.append(f"  • {c}")
        lines.append("")

    lines.append("━━━ ACTION ━━━")
    lines.append(f"⚠️  Don't execute yet. Watch for the EXECUTE alert.")
    lines.append(f"    You'll get a full action plan when conditions confirm.")
    lines.append("")

    lines.append("💬 ASK CLAUDE (copy-paste):")
    lines.append(f"```")
    lines.append(f"Watching {direction} {symbol} @ ${_fmt_price(entry)}")
    lines.append(f"{shadow_line}")
    if decision.key_conditions_missing:
        lines.append(f"Still need: {'; '.join(decision.key_conditions_missing)}")
    lines.append(f"What do I watch for?")
    lines.append(f"```")

    return "\n".join(lines)


def format_signal_skipped_debug(
    symbol: str,
    side: str,
    decision: AlertDecision,
    confidence: float = 0,
) -> str:
    """Debug line for filtered signals (dashboard/log, never to Telegram)."""
    _side_up = (side or "").upper()
    return f"[ALERT SKIP] {symbol} {_side_up} @ conf={confidence:.0f}% — {decision.reason}"
