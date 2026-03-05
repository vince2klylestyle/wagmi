"""
Sandbox: Safe backtest-style evaluation of proposed strategies.

Runs proposals against recent historical data to estimate performance
before any live deployment. This is the safety layer between
"the LLM had an idea" and "we're actually trading it".
"""

import json
import logging
import os
import time
from typing import Dict, Any, Optional, List

from .proposals import StrategyProposal, ProposalStatus
from .research_agent import save_proposal

logger = logging.getLogger("bot.llm.strategy_discovery.sandbox")

# Minimum requirements for a proposal to pass sandbox
_MIN_SAMPLE_SIZE = 10
_MIN_WIN_RATE = 0.40
_MIN_PROFIT_FACTOR = 1.0
_MAX_DRAWDOWN_PCT = 15.0


def evaluate_proposal(
    proposal: StrategyProposal,
    historical_trades: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Evaluate a strategy proposal against historical data.

    This is a simplified backtest that checks whether the proposal's
    conditions would have generated profitable trades in recent history.

    Returns sandbox results dict with pass/fail and metrics.
    """
    proposal.status = ProposalStatus.SANDBOX_PENDING
    save_proposal(proposal)

    if not historical_trades:
        historical_trades = _load_recent_trades()

    if len(historical_trades) < _MIN_SAMPLE_SIZE:
        result = {
            "passed": False,
            "reason": f"Insufficient data: {len(historical_trades)} trades (need {_MIN_SAMPLE_SIZE})",
            "sample_size": len(historical_trades),
        }
        proposal.status = ProposalStatus.SANDBOX_FAILED
        proposal.sandbox_results = result
        save_proposal(proposal)
        return result

    # Filter trades by target regimes and symbols
    matching = _filter_matching_trades(historical_trades, proposal)

    if len(matching) < _MIN_SAMPLE_SIZE:
        result = {
            "passed": False,
            "reason": f"Only {len(matching)} matching trades (need {_MIN_SAMPLE_SIZE})",
            "sample_size": len(matching),
            "total_evaluated": len(historical_trades),
        }
        proposal.status = ProposalStatus.SANDBOX_FAILED
        proposal.sandbox_results = result
        save_proposal(proposal)
        return result

    # Compute performance metrics
    metrics = _compute_metrics(matching)

    # Check against thresholds
    passed = True
    reasons = []

    if metrics["win_rate"] < _MIN_WIN_RATE:
        passed = False
        reasons.append(f"Win rate {metrics['win_rate']:.1%} < {_MIN_WIN_RATE:.1%}")

    if metrics["profit_factor"] < _MIN_PROFIT_FACTOR:
        passed = False
        reasons.append(f"Profit factor {metrics['profit_factor']:.2f} < {_MIN_PROFIT_FACTOR}")

    if metrics["max_drawdown_pct"] > _MAX_DRAWDOWN_PCT:
        passed = False
        reasons.append(f"Max DD {metrics['max_drawdown_pct']:.1f}% > {_MAX_DRAWDOWN_PCT}%")

    result = {
        "passed": passed,
        "reason": "; ".join(reasons) if reasons else "All checks passed",
        "metrics": metrics,
        "sample_size": len(matching),
        "total_evaluated": len(historical_trades),
        "evaluated_at": time.time(),
    }

    proposal.status = ProposalStatus.SANDBOX_PASSED if passed else ProposalStatus.SANDBOX_FAILED
    proposal.sandbox_results = result
    save_proposal(proposal)

    logger.info(
        f"[SANDBOX] {proposal.name}: {'PASSED' if passed else 'FAILED'} "
        f"(WR={metrics['win_rate']:.1%} PF={metrics['profit_factor']:.2f} "
        f"DD={metrics['max_drawdown_pct']:.1f}%)"
    )

    return result


def _filter_matching_trades(
    trades: List[Dict[str, Any]],
    proposal: StrategyProposal,
) -> List[Dict[str, Any]]:
    """Filter historical trades that match the proposal's regime/symbol criteria."""
    matching = []
    for t in trades:
        regime = t.get("regime", "unknown")
        symbol = t.get("symbol", "")

        # Skip if trade is in an avoid regime
        if regime in proposal.avoid_regimes:
            continue

        # If best_regimes specified, only count those
        if proposal.best_regimes and regime not in proposal.best_regimes:
            continue

        # If target_symbols specified, filter
        if proposal.target_symbols and symbol not in proposal.target_symbols:
            continue

        matching.append(t)
    return matching


def _compute_metrics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute performance metrics from a list of trade dicts."""
    wins = 0
    losses = 0
    total_profit = 0.0
    total_loss = 0.0
    pnl_series = []
    running_pnl = 0.0
    peak_pnl = 0.0
    max_dd = 0.0

    for t in trades:
        pnl = float(t.get("realized_pnl", t.get("pnl", 0)))
        if pnl > 0:
            wins += 1
            total_profit += pnl
        elif pnl < 0:
            losses += 1
            total_loss += abs(pnl)

        running_pnl += pnl
        peak_pnl = max(peak_pnl, running_pnl)
        dd = peak_pnl - running_pnl
        max_dd = max(max_dd, dd)
        pnl_series.append(running_pnl)

    total = wins + losses
    win_rate = wins / total if total > 0 else 0.0
    profit_factor = total_profit / total_loss if total_loss > 0 else float("inf")
    avg_win = total_profit / wins if wins > 0 else 0.0
    avg_loss = total_loss / losses if losses > 0 else 0.0

    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "profit_factor": round(profit_factor, 2),
        "total_pnl": round(running_pnl, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "max_drawdown_pct": round(max_dd, 2),
    }


def _load_recent_trades() -> List[Dict[str, Any]]:
    """Load recent trades from candidate log for sandbox evaluation."""
    candidate_log = os.path.join("data", "analysis", "trade_candidates.csv")
    if not os.path.exists(candidate_log):
        return []

    import csv
    trades = []
    try:
        with open(candidate_log, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("outcome"):  # Only completed trades
                    trades.append(row)
    except Exception:
        pass
    return trades[-500:]  # Last 500 trades


def promote_to_approval(proposal_id: str) -> Optional[StrategyProposal]:
    """Move a sandbox-passed proposal to awaiting_approval status."""
    from .research_agent import load_proposal
    proposal = load_proposal(proposal_id)
    if not proposal:
        return None
    if proposal.status != ProposalStatus.SANDBOX_PASSED:
        logger.warning(f"Cannot promote {proposal_id}: status is {proposal.status.value}")
        return None
    proposal.status = ProposalStatus.AWAITING_APPROVAL
    save_proposal(proposal)
    return proposal


def approve_proposal(proposal_id: str, notes: str = "") -> Optional[StrategyProposal]:
    """Human approval of a proposal (via Telegram)."""
    from .research_agent import load_proposal
    proposal = load_proposal(proposal_id)
    if not proposal:
        return None
    if proposal.status != ProposalStatus.AWAITING_APPROVAL:
        logger.warning(f"Cannot approve {proposal_id}: status is {proposal.status.value}")
        return None
    proposal.status = ProposalStatus.APPROVED
    proposal.approval_notes = notes
    save_proposal(proposal)
    logger.info(f"[SANDBOX] Proposal approved: {proposal.name} ({proposal_id})")
    return proposal


def reject_proposal(proposal_id: str, notes: str = "") -> Optional[StrategyProposal]:
    """Human rejection of a proposal."""
    from .research_agent import load_proposal
    proposal = load_proposal(proposal_id)
    if not proposal:
        return None
    proposal.status = ProposalStatus.REJECTED
    proposal.approval_notes = notes
    save_proposal(proposal)
    return proposal
