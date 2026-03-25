"""
Monte Carlo Ruin Probability Checker

Runs fast Monte Carlo simulations before each trade to validate that
proposed sizing won't lead to account ruin. Pure Python for portability.

Usage:
    from execution.monte_carlo_ruin import is_size_safe, simulate_ruin

    safe, stats = is_size_safe(win_rate=0.55, payoff_ratio=2.0, risk_pct=5.0)
    if not safe:
        # Downsize the trade
        ...
"""

import random
import time
from dataclasses import dataclass
from typing import Tuple


# Ruin threshold: equity drops below this fraction of starting equity
RUIN_THRESHOLD = 0.10  # 10% of starting equity
# Maximum acceptable ruin probability before downsizing
MAX_RUIN_PROBABILITY = 0.01  # 1%


@dataclass
class RuinSimulationResult:
    """Results from a Monte Carlo ruin simulation."""
    ruin_probability: float       # Fraction of paths that hit ruin (0.0 - 1.0)
    median_equity: float          # Median final equity across all paths
    worst_path_equity: float      # Lowest final equity seen
    best_path_equity: float       # Highest final equity seen
    percentile_5th: float         # 5th percentile final equity
    percentile_95th: float        # 95th percentile final equity
    num_simulations: int          # How many paths were simulated
    num_trades: int               # Trades per path
    elapsed_ms: float             # Wall-clock time in milliseconds

    def to_dict(self) -> dict:
        return {
            "ruin_probability": round(self.ruin_probability, 6),
            "ruin_probability_pct": round(self.ruin_probability * 100, 4),
            "median_equity": round(self.median_equity, 4),
            "worst_path_equity": round(self.worst_path_equity, 4),
            "best_path_equity": round(self.best_path_equity, 4),
            "percentile_5th": round(self.percentile_5th, 4),
            "percentile_95th": round(self.percentile_95th, 4),
            "num_simulations": self.num_simulations,
            "num_trades": self.num_trades,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }


def simulate_ruin(
    win_rate: float,
    payoff_ratio: float,
    risk_per_trade_pct: float,
    num_simulations: int = 1000,
    num_trades: int = 50,
    seed: int | None = None,
) -> RuinSimulationResult:
    """
    Run Monte Carlo simulation of trade sequences to estimate ruin probability.

    Args:
        win_rate: Probability of winning each trade (0.0 - 1.0).
        payoff_ratio: Reward-to-risk ratio (e.g., 2.0 means win 2R, lose 1R).
        risk_per_trade_pct: Percentage of CURRENT equity risked per trade (e.g., 5.0 = 5%).
        num_simulations: Number of random equity paths to simulate.
        num_trades: Number of trades per simulated path.
        seed: Optional RNG seed for reproducibility.

    Returns:
        RuinSimulationResult with ruin probability and equity distribution stats.
    """
    # Validate inputs
    win_rate = max(0.0, min(1.0, float(win_rate)))
    payoff_ratio = max(0.0, float(payoff_ratio))
    risk_per_trade_pct = max(0.0, min(100.0, float(risk_per_trade_pct)))
    num_simulations = max(1, int(num_simulations))
    num_trades = max(1, int(num_trades))

    risk_fraction = risk_per_trade_pct / 100.0
    ruin_level = RUIN_THRESHOLD  # equity <= this fraction of start = ruin

    rng = random.Random(seed)
    start_time = time.perf_counter()

    final_equities = []
    ruin_count = 0

    for _ in range(num_simulations):
        equity = 1.0  # Normalized starting equity
        ruined = False

        for _ in range(num_trades):
            risk_amount = equity * risk_fraction

            if rng.random() < win_rate:
                # Win: gain risk_amount * payoff_ratio
                equity += risk_amount * payoff_ratio
            else:
                # Loss: lose risk_amount
                equity -= risk_amount

            # Check ruin
            if equity <= ruin_level:
                ruined = True
                equity = max(equity, 0.0)
                break

        if ruined:
            ruin_count += 1
        final_equities.append(equity)

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    # Sort for percentile calculations
    final_equities.sort()
    n = len(final_equities)

    def percentile(sorted_list: list, pct: float) -> float:
        """Get percentile value from a sorted list."""
        idx = pct / 100.0 * (len(sorted_list) - 1)
        lower = int(idx)
        upper = min(lower + 1, len(sorted_list) - 1)
        frac = idx - lower
        return sorted_list[lower] * (1 - frac) + sorted_list[upper] * frac

    return RuinSimulationResult(
        ruin_probability=ruin_count / num_simulations,
        median_equity=percentile(final_equities, 50),
        worst_path_equity=final_equities[0],
        best_path_equity=final_equities[-1],
        percentile_5th=percentile(final_equities, 5),
        percentile_95th=percentile(final_equities, 95),
        num_simulations=num_simulations,
        num_trades=num_trades,
        elapsed_ms=elapsed_ms,
    )


def is_size_safe(
    win_rate: float,
    payoff_ratio: float,
    risk_pct: float,
    num_simulations: int = 1000,
    num_trades: int = 50,
    max_ruin_pct: float = MAX_RUIN_PROBABILITY,
    seed: int | None = None,
) -> Tuple[bool, dict]:
    """
    Convenience function: check if a proposed trade size is safe.

    Args:
        win_rate: Win probability (0.0 - 1.0).
        payoff_ratio: Reward:risk ratio.
        risk_pct: Percent of equity risked per trade.
        num_simulations: Monte Carlo paths.
        num_trades: Trades per path.
        max_ruin_pct: Maximum acceptable ruin probability (0.0 - 1.0). Default 1%.
        seed: Optional RNG seed.

    Returns:
        Tuple of (is_safe: bool, stats: dict).
        is_safe is True if ruin_probability <= max_ruin_pct.
    """
    result = simulate_ruin(
        win_rate=win_rate,
        payoff_ratio=payoff_ratio,
        risk_per_trade_pct=risk_pct,
        num_simulations=num_simulations,
        num_trades=num_trades,
        seed=seed,
    )

    is_safe = result.ruin_probability <= max_ruin_pct
    stats = result.to_dict()
    stats["is_safe"] = is_safe
    stats["max_ruin_pct"] = round(max_ruin_pct * 100, 4)

    return is_safe, stats
