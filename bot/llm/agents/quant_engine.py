"""
Quant Engine: deterministic math tools for agent decision-making.

LLMs should NEVER do math. They call these functions and get exact results.
All functions are pure, deterministic, and use only stdlib (math, statistics).

Usage in agent pipeline:
    from llm.agents.quant_engine import QuantEngine
    engine = QuantEngine(equity=1000)
    metrics = engine.compute_trade_metrics(entry=89.0, sl=87.5, tp1=92.0, ...)
"""

import math
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("bot.llm.agents.quant_engine")


# ─────────────────────────────────────────────────────────────────────────────
# POSITION SIZING (Kelly Criterion)
# ─────────────────────────────────────────────────────────────────────────────

def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Full Kelly fraction. Returns 0 if negative edge.

    Args:
        win_rate: Probability of winning (0-1)
        avg_win: Average win amount (positive)
        avg_loss: Average loss amount (positive)

    Returns: Optimal fraction of bankroll to risk (0-1)
    """
    if avg_loss <= 0 or avg_win <= 0 or win_rate <= 0 or win_rate >= 1:
        return 0.0
    b = avg_win / avg_loss  # odds ratio
    f = (win_rate * b - (1 - win_rate)) / b
    return max(0.0, f)


def half_kelly(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Half-Kelly for safety. Reduces variance significantly."""
    return kelly_fraction(win_rate, avg_win, avg_loss) / 2.0


def optimal_position_size(
    equity: float,
    kelly_f: float,
    max_risk_pct: float = 0.02,
    leverage: float = 1.0,
) -> float:
    """Dollar amount to risk, capped by max_risk_pct of equity.

    Args:
        equity: Total account equity
        kelly_f: Kelly fraction (from half_kelly or kelly_fraction)
        max_risk_pct: Maximum risk as fraction of equity (default 2%)
        leverage: Applied leverage multiplier

    Returns: Dollar amount to allocate to this position
    """
    if equity <= 0 or kelly_f <= 0:
        return 0.0
    kelly_size = equity * kelly_f
    max_size = equity * max_risk_pct
    return min(kelly_size, max_size) * leverage


# ─────────────────────────────────────────────────────────────────────────────
# EXPECTED VALUE
# ─────────────────────────────────────────────────────────────────────────────

def expected_value(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """EV per trade in dollar terms.

    Positive = edge exists. Negative = losing proposition.
    """
    return (win_rate * avg_win) - ((1 - win_rate) * avg_loss)


def expected_value_pct(win_rate: float, avg_win_pct: float, avg_loss_pct: float) -> float:
    """EV per trade in percentage terms."""
    return (win_rate * avg_win_pct) - ((1 - win_rate) * avg_loss_pct)


def breakeven_win_rate(avg_win: float, avg_loss: float) -> float:
    """Win rate needed to break even given avg win/loss sizes."""
    if avg_win + avg_loss <= 0:
        return 1.0
    return avg_loss / (avg_win + avg_loss)


# ─────────────────────────────────────────────────────────────────────────────
# RISK METRICS
# ─────────────────────────────────────────────────────────────────────────────

def value_at_risk(returns: List[float], confidence: float = 0.95) -> float:
    """Historical VaR at given confidence level.

    Returns the loss threshold at the given percentile (negative number).
    """
    if not returns or len(returns) < 2:
        return 0.0
    sorted_r = sorted(returns)
    idx = int(len(sorted_r) * (1 - confidence))
    idx = max(0, min(idx, len(sorted_r) - 1))
    return sorted_r[idx]


def conditional_var(returns: List[float], confidence: float = 0.95) -> float:
    """CVaR (Expected Shortfall) — average loss beyond VaR.

    Answers: "When things go bad, how bad on average?"
    """
    if not returns or len(returns) < 2:
        return 0.0
    sorted_r = sorted(returns)
    cutoff = int(len(sorted_r) * (1 - confidence))
    cutoff = max(1, cutoff)
    tail = sorted_r[:cutoff]
    return sum(tail) / len(tail) if tail else 0.0


def max_drawdown(equity_curve: List[float]) -> Tuple[float, int, int]:
    """Max drawdown percentage, peak index, trough index.

    Returns: (drawdown_pct, peak_idx, trough_idx)
    """
    if not equity_curve or len(equity_curve) < 2:
        return (0.0, 0, 0)

    peak = equity_curve[0]
    peak_idx = 0
    max_dd = 0.0
    max_dd_peak = 0
    max_dd_trough = 0

    for i, val in enumerate(equity_curve):
        if val > peak:
            peak = val
            peak_idx = i
        if peak > 0:
            dd = (peak - val) / peak
            if dd > max_dd:
                max_dd = dd
                max_dd_peak = peak_idx
                max_dd_trough = i

    return (max_dd, max_dd_peak, max_dd_trough)


def drawdown_duration(equity_curve: List[float]) -> int:
    """Longest drawdown duration in periods."""
    if not equity_curve or len(equity_curve) < 2:
        return 0

    peak = equity_curve[0]
    current_dd_len = 0
    max_dd_len = 0

    for val in equity_curve:
        if val >= peak:
            peak = val
            current_dd_len = 0
        else:
            current_dd_len += 1
            max_dd_len = max(max_dd_len, current_dd_len)

    return max_dd_len


def sharpe_ratio(
    returns: List[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Annualized Sharpe ratio."""
    if not returns or len(returns) < 2:
        return 0.0
    n = len(returns)
    mean_r = sum(returns) / n
    excess = mean_r - risk_free_rate / periods_per_year
    variance = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(variance) if variance > 0 else 0.0
    if std == 0:
        return 0.0
    return (excess / std) * math.sqrt(periods_per_year)


def sortino_ratio(
    returns: List[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Annualized Sortino ratio (downside deviation only)."""
    if not returns or len(returns) < 2:
        return 0.0
    n = len(returns)
    mean_r = sum(returns) / n
    excess = mean_r - risk_free_rate / periods_per_year
    downside = [r for r in returns if r < 0]
    if not downside:
        return 10.0  # No downside = very high ratio (capped)
    down_var = sum(r ** 2 for r in downside) / len(downside)
    down_std = math.sqrt(down_var) if down_var > 0 else 0.0
    if down_std == 0:
        return 0.0
    return (excess / down_std) * math.sqrt(periods_per_year)


def calmar_ratio(returns: List[float], periods_per_year: int = 252) -> float:
    """Calmar ratio = annualized return / max drawdown."""
    if not returns or len(returns) < 2:
        return 0.0
    # Build equity curve from returns
    equity = [1.0]
    for r in returns:
        equity.append(equity[-1] * (1 + r))
    dd, _, _ = max_drawdown(equity)
    if dd == 0:
        return 10.0
    annual_return = (equity[-1] / equity[0]) ** (periods_per_year / len(returns)) - 1
    return annual_return / dd


# ─────────────────────────────────────────────────────────────────────────────
# CORRELATION & PORTFOLIO
# ─────────────────────────────────────────────────────────────────────────────

def correlation_matrix(returns_dict: Dict[str, List[float]]) -> Dict[str, Dict[str, float]]:
    """Pairwise correlation matrix for multiple symbols.

    Args:
        returns_dict: {symbol: [returns_list]}

    Returns: {sym1: {sym2: correlation}}
    """
    symbols = list(returns_dict.keys())
    result: Dict[str, Dict[str, float]] = {}

    for s1 in symbols:
        result[s1] = {}
        for s2 in symbols:
            if s1 == s2:
                result[s1][s2] = 1.0
            else:
                result[s1][s2] = _pearson(returns_dict[s1], returns_dict[s2])

    return result


def _pearson(x: List[float], y: List[float]) -> float:
    """Pearson correlation coefficient."""
    n = min(len(x), len(y))
    if n < 3:
        return 0.0
    x, y = x[:n], y[:n]
    mx = sum(x) / n
    my = sum(y) / n
    cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / (n - 1)
    sx = math.sqrt(sum((xi - mx) ** 2 for xi in x) / (n - 1))
    sy = math.sqrt(sum((yi - my) ** 2 for yi in y) / (n - 1))
    if sx == 0 or sy == 0:
        return 0.0
    return max(-1.0, min(1.0, cov / (sx * sy)))


def concentration_risk(positions: Dict[str, float]) -> float:
    """Herfindahl index of position concentration.

    0 = perfectly diversified, 1 = single position.

    Args:
        positions: {symbol: position_value}
    """
    if not positions:
        return 0.0
    total = sum(abs(v) for v in positions.values())
    if total == 0:
        return 0.0
    weights = [abs(v) / total for v in positions.values()]
    return sum(w ** 2 for w in weights)


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL QUALITY
# ─────────────────────────────────────────────────────────────────────────────

def signal_quality_score(
    win_rate: float,
    profit_factor: float,
    sample_size: int,
    avg_duration_hours: float,
    max_consecutive_losses: int,
) -> float:
    """Composite signal quality score 0-100.

    Weights: win_rate(30), profit_factor(25), sample_size(20),
             duration_efficiency(15), streak_safety(10)
    """
    # Win rate component (30 pts)
    wr_score = min(30, max(0, (win_rate - 0.40) / 0.30 * 30))

    # Profit factor component (25 pts)
    pf_score = min(25, max(0, (profit_factor - 1.0) / 1.5 * 25))

    # Sample size component (20 pts) — log scale
    if sample_size <= 0:
        ss_score = 0.0
    else:
        ss_score = min(20, math.log10(sample_size + 1) / math.log10(100) * 20)

    # Duration efficiency (15 pts) — shorter = better for perps
    if avg_duration_hours <= 0:
        dur_score = 0.0
    elif avg_duration_hours <= 2:
        dur_score = 15.0  # Scalp — most efficient
    elif avg_duration_hours <= 6:
        dur_score = 12.0
    elif avg_duration_hours <= 12:
        dur_score = 8.0
    else:
        dur_score = max(0, 15 - avg_duration_hours * 0.5)

    # Streak safety (10 pts) — fewer consecutive losses = better
    streak_score = max(0, 10 - max_consecutive_losses * 2)

    return round(wr_score + pf_score + ss_score + dur_score + streak_score, 1)


def regime_edge(
    win_rate: float,
    sample_size: int,
    baseline_wr: float = 0.50,
) -> Dict[str, Any]:
    """Statistical edge with Wilson score confidence interval.

    Returns whether the edge is statistically significant.
    """
    if sample_size <= 0:
        return {"edge": 0.0, "significant": False, "ci_lower": 0.0, "ci_upper": 1.0, "n": 0}

    # Wilson score interval (95% CI)
    z = 1.96  # 95% confidence
    n = sample_size
    p_hat = win_rate

    denom = 1 + z ** 2 / n
    center = (p_hat + z ** 2 / (2 * n)) / denom
    spread = z * math.sqrt((p_hat * (1 - p_hat) + z ** 2 / (4 * n)) / n) / denom

    ci_lower = max(0, center - spread)
    ci_upper = min(1, center + spread)

    edge = win_rate - baseline_wr
    significant = ci_lower > baseline_wr  # Lower bound above baseline = significant

    return {
        "edge": round(edge, 4),
        "significant": significant,
        "ci_lower": round(ci_lower, 4),
        "ci_upper": round(ci_upper, 4),
        "n": n,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FUNDING & COST
# ─────────────────────────────────────────────────────────────────────────────

def funding_projection(rate_8h: float, position_size: float, hours: int) -> float:
    """Project funding cost over hold period.

    Args:
        rate_8h: 8-hour funding rate (e.g., 0.01 = 1%)
        position_size: Notional position size in USD
        hours: Expected hold duration in hours

    Returns: Total projected funding cost (positive = cost, negative = earned)
    """
    periods = hours / 8.0
    return rate_8h * position_size * periods


def breakeven_after_costs(
    entry: float,
    side: str,
    funding_rate: float,
    fee_rate: float,
    hold_hours: int,
) -> float:
    """Price must move this much (%) just to break even.

    Accounts for entry fee, exit fee, and projected funding.
    """
    # Entry + exit fees
    total_fee_pct = fee_rate * 2  # Entry and exit

    # Funding cost as percentage
    funding_periods = hold_hours / 8.0
    funding_pct = abs(funding_rate) * funding_periods

    return total_fee_pct + funding_pct


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE: ALL-IN-ONE TRADE METRICS
# ─────────────────────────────────────────────────────────────────────────────

def compute_trade_metrics(
    equity: float,
    entry: float,
    sl: float,
    tp1: float,
    side: str,
    win_rate: float,
    avg_win_pct: float = 0.0,
    avg_loss_pct: float = 0.0,
    funding_rate: float = 0.0,
    fee_rate: float = 0.0007,
    leverage: float = 1.0,
    hold_hours: int = 4,
) -> Dict[str, Any]:
    """One-call summary of all metrics for a proposed trade.

    This is what agents call before making decisions.
    Returns a dict with all computed metrics.
    """
    # Risk/Reward from levels
    if side.upper() in ("BUY", "LONG"):
        risk = abs(entry - sl)
        reward = abs(tp1 - entry)
    else:
        risk = abs(sl - entry)
        reward = abs(entry - tp1)

    rr = reward / risk if risk > 0 else 0.0

    # Auto-compute avg_win/loss if not provided
    if avg_win_pct <= 0 and entry > 0:
        avg_win_pct = (reward / entry) * 100
    if avg_loss_pct <= 0 and entry > 0:
        avg_loss_pct = (risk / entry) * 100

    # Core metrics
    kf = half_kelly(win_rate, avg_win_pct, avg_loss_pct)
    ev = expected_value_pct(win_rate, avg_win_pct, avg_loss_pct)
    be_wr = breakeven_win_rate(avg_win_pct, avg_loss_pct)
    pos_size = optimal_position_size(equity, kf, leverage=leverage)

    # Cost analysis
    funding_cost = funding_projection(funding_rate, pos_size, hold_hours)
    be_move = breakeven_after_costs(entry, side, funding_rate, fee_rate, hold_hours)

    return {
        "risk_reward": round(rr, 2),
        "half_kelly": round(kf, 4),
        "ev_per_trade_pct": round(ev, 3),
        "breakeven_wr": round(be_wr, 3),
        "position_size_usd": round(pos_size, 2),
        "risk_pct": round(avg_loss_pct, 2),
        "reward_pct": round(avg_win_pct, 2),
        "funding_cost_projected": round(funding_cost, 4),
        "breakeven_move_pct": round(be_move, 4),
        "edge_exists": ev > 0,
        "kelly_says_trade": kf > 0.01,
    }


# ─────────────────────────────────────────────────────────────────────────────
# QUANT ENGINE CLASS (stateful wrapper)
# ─────────────────────────────────────────────────────────────────────────────

class QuantEngine:
    """Stateful quant engine that caches equity and portfolio data.

    Usage:
        engine = QuantEngine(equity=1000)
        metrics = engine.compute_trade_metrics(entry=89.0, sl=87.5, tp1=92.0, ...)
    """

    def __init__(self, equity: float = 1000.0):
        self.equity = equity
        self.positions: Dict[str, float] = {}
        self.returns_history: Dict[str, List[float]] = {}

    def update_equity(self, equity: float) -> None:
        self.equity = equity

    def add_position(self, symbol: str, value: float) -> None:
        self.positions[symbol] = value

    def add_returns(self, symbol: str, returns: List[float]) -> None:
        self.returns_history[symbol] = returns

    # Delegate to module-level functions with cached state
    def kelly_fraction(self, wr: float, avg_win: float, avg_loss: float) -> float:
        return kelly_fraction(wr, avg_win, avg_loss)

    def half_kelly(self, wr: float, avg_win: float, avg_loss: float) -> float:
        return half_kelly(wr, avg_win, avg_loss)

    def optimal_position_size(self, kelly_f: float, max_risk_pct: float = 0.02, leverage: float = 1.0) -> float:
        return optimal_position_size(self.equity, kelly_f, max_risk_pct, leverage)

    def expected_value(self, wr: float, avg_win: float, avg_loss: float) -> float:
        return expected_value(wr, avg_win, avg_loss)

    def expected_value_pct(self, wr: float, avg_win_pct: float, avg_loss_pct: float) -> float:
        return expected_value_pct(wr, avg_win_pct, avg_loss_pct)

    def breakeven_win_rate(self, avg_win: float, avg_loss: float) -> float:
        return breakeven_win_rate(avg_win, avg_loss)

    def funding_projection(self, rate_8h: float, position_size: float, hours: int) -> float:
        return funding_projection(rate_8h, position_size, hours)

    def compute_trade_metrics(self, **kwargs) -> Dict[str, Any]:
        kwargs.setdefault("equity", self.equity)
        return compute_trade_metrics(**kwargs)

    def portfolio_concentration(self) -> float:
        return concentration_risk(self.positions)

    def portfolio_correlation(self) -> Dict[str, Dict[str, float]]:
        return correlation_matrix(self.returns_history)

    def sharpe(self, returns: List[float]) -> float:
        return sharpe_ratio(returns)

    def sortino(self, returns: List[float]) -> float:
        return sortino_ratio(returns)

    def var(self, returns: List[float], confidence: float = 0.95) -> float:
        return value_at_risk(returns, confidence)

    def cvar(self, returns: List[float], confidence: float = 0.95) -> float:
        return conditional_var(returns, confidence)


__all__ = [
    # Position sizing
    "kelly_fraction", "half_kelly", "optimal_position_size",
    # Expected value
    "expected_value", "expected_value_pct", "breakeven_win_rate",
    # Risk metrics
    "value_at_risk", "conditional_var", "max_drawdown", "drawdown_duration",
    "sharpe_ratio", "sortino_ratio", "calmar_ratio",
    # Portfolio
    "correlation_matrix", "concentration_risk",
    # Signal quality
    "signal_quality_score", "regime_edge",
    # Funding
    "funding_projection", "breakeven_after_costs",
    # Convenience
    "compute_trade_metrics",
    # Class
    "QuantEngine",
]
