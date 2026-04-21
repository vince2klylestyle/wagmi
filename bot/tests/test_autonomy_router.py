"""
Smoke tests for llm/autonomy_router.py.

Covers all 6 LLM autonomy modes (OFF, ADVISORY, VETO_ONLY, SIZING,
DIRECTION, FULL) plus helper predicates and divergence tracking.
"""

import pytest

from llm.autonomy import LLMMode
from llm.autonomy_router import (
    apply_autonomy_mode,
    get_mode_description,
    can_llm_flip,
    can_llm_scale_size,
    is_llm_active,
    get_divergence_rate,
    get_divergence_stats,
    _divergence_history,
)
from llm.decision_types import LLMDecision, StrategyWeights


def _baseline(action="long", size=1.0, confidence=0.7, regime="trend"):
    return {
        "action": action,
        "size": size,
        "confidence": confidence,
        "regime": regime,
        "entry": 100.0,
        "sl": 95.0,
        "tp": 110.0,
    }


def _llm(action="proceed", confidence=0.7, regime="trend",
         size_mult=1.0, notes="test", entry_adj=None):
    return LLMDecision(
        action=action,
        confidence=confidence,
        regime=regime,
        strategy_weights=StrategyWeights(),
        memory_update=None,
        notes=notes,
        size_multiplier=size_mult,
        entry_adjustment=entry_adj,
    )


# ── Mode: OFF ────────────────────────────────────────────────


class TestModeOff:
    def test_llm_ignored(self):
        d = apply_autonomy_mode(LLMMode.OFF, _baseline(), _llm(action="flat"))
        assert d["action"] == "long"  # baseline not overridden
        assert d["llm_veto"] is False
        assert d["mode_used"] == "OFF"
        assert d["source"] == "baseline"

    def test_llm_none(self):
        d = apply_autonomy_mode(LLMMode.OFF, _baseline(), None)
        assert d["action"] == "long"
        assert d["mode_used"] == "OFF"


# ── Mode: ADVISORY ───────────────────────────────────────────


class TestModeAdvisory:
    def setup_method(self):
        _divergence_history.clear()

    def test_baseline_preserved(self):
        d = apply_autonomy_mode(LLMMode.ADVISORY, _baseline(),
                                _llm(action="flat"))
        # Even though LLM said flat, baseline action wins
        assert d["action"] == "long"
        assert d["llm_veto"] is False
        assert d["mode_used"] == "ADVISORY"

    def test_llm_logged(self):
        d = apply_autonomy_mode(LLMMode.ADVISORY, _baseline(),
                                _llm(action="proceed"))
        assert "llm_decision_logged" in d

    def test_divergence_tracked(self):
        # 5 disagreements (action != "proceed")
        for _ in range(5):
            apply_autonomy_mode(LLMMode.ADVISORY, _baseline(),
                                _llm(action="flat"))
        rate = get_divergence_rate()
        assert rate > 0.5  # all were disagreements
        stats = get_divergence_stats()
        assert stats["total"] == 5
        assert stats["divergence_rate"] > 0.5

    def test_none_llm(self):
        d = apply_autonomy_mode(LLMMode.ADVISORY, _baseline(), None)
        assert d["action"] == "long"
        assert "llm_decision_logged" not in d


# ── Mode: VETO_ONLY ──────────────────────────────────────────


class TestModeVetoOnly:
    def test_veto_on_flat(self):
        d = apply_autonomy_mode(LLMMode.VETO_ONLY, _baseline(),
                                _llm(action="flat", notes="too risky"))
        assert d["action"] == "flat"
        assert d["llm_veto"] is True
        assert "veto_reason" in d

    def test_flip_downgraded_to_flat(self):
        d = apply_autonomy_mode(LLMMode.VETO_ONLY, _baseline(),
                                _llm(action="flip", confidence=0.8))
        assert d["action"] == "flat"
        assert d["llm_veto"] is True

    def test_proceed_keeps_baseline(self):
        d = apply_autonomy_mode(LLMMode.VETO_ONLY, _baseline(),
                                _llm(action="proceed", confidence=0.75))
        assert d["action"] == "long"
        assert d["llm_veto"] is False

    def test_weak_approval_scales_size(self):
        d = apply_autonomy_mode(LLMMode.VETO_ONLY, _baseline(),
                                _llm(action="proceed", confidence=0.50))
        assert d.get("size_multiplier") == 0.6

    def test_moderate_approval_scales_size(self):
        d = apply_autonomy_mode(LLMMode.VETO_ONLY, _baseline(),
                                _llm(action="proceed", confidence=0.60))
        assert d.get("size_multiplier") == 0.8

    def test_none_llm_falls_back(self):
        d = apply_autonomy_mode(LLMMode.VETO_ONLY, _baseline(), None)
        assert d["action"] == "long"
        assert d["llm_veto"] is False


# ── Mode: SIZING ─────────────────────────────────────────────


class TestModeSizing:
    def test_scale_size(self):
        d = apply_autonomy_mode(LLMMode.SIZING, _baseline(size=1.0),
                                _llm(action="proceed", size_mult=1.5))
        assert d["size"] == pytest.approx(1.5)
        assert d["size_multiplier"] == 1.5

    def test_clamp_size_high(self):
        d = apply_autonomy_mode(LLMMode.SIZING, _baseline(size=1.0),
                                _llm(action="proceed", size_mult=5.0))
        # Clamped to 2.0
        assert d["size_multiplier"] == 2.0
        assert d["size"] == pytest.approx(2.0)

    def test_clamp_size_low(self):
        d = apply_autonomy_mode(LLMMode.SIZING, _baseline(size=1.0),
                                _llm(action="proceed", size_mult=-0.5))
        assert d["size_multiplier"] == 0.0

    def test_veto_on_flat(self):
        d = apply_autonomy_mode(LLMMode.SIZING, _baseline(),
                                _llm(action="flat"))
        assert d["action"] == "flat"
        assert d["llm_veto"] is True

    def test_flip_downgraded(self):
        d = apply_autonomy_mode(LLMMode.SIZING, _baseline(),
                                _llm(action="flip"))
        assert d["action"] == "flat"
        assert d["llm_veto"] is True

    def test_confidence_upgraded(self):
        d = apply_autonomy_mode(LLMMode.SIZING, _baseline(confidence=0.5),
                                _llm(action="proceed", confidence=0.9))
        assert d["confidence"] == pytest.approx(0.9)


# ── Mode: DIRECTION ──────────────────────────────────────────


class TestModeDirection:
    def test_proceed_keeps_baseline_side(self):
        d = apply_autonomy_mode(LLMMode.DIRECTION,
                                _baseline(action="long"),
                                _llm(action="proceed", size_mult=1.2))
        assert d["action"] == "long"
        assert d["llm_veto"] is False

    def test_flip_with_high_confidence(self):
        d = apply_autonomy_mode(LLMMode.DIRECTION,
                                _baseline(action="long"),
                                _llm(action="flip", confidence=0.75))
        assert d["action"] == "short"
        assert d["llm_direction"] == "flip"

    def test_flip_rejected_low_confidence(self):
        d = apply_autonomy_mode(LLMMode.DIRECTION,
                                _baseline(action="long"),
                                _llm(action="flip", confidence=0.55))
        assert d["action"] == "flat"
        assert d["llm_veto"] is True

    def test_flat_vetoes(self):
        d = apply_autonomy_mode(LLMMode.DIRECTION, _baseline(),
                                _llm(action="flat"))
        assert d["action"] == "flat"
        assert d["llm_veto"] is True


# ── Mode: FULL ───────────────────────────────────────────────


class TestModeFull:
    def test_full_override_size_and_conf(self):
        d = apply_autonomy_mode(
            LLMMode.FULL,
            _baseline(action="long", size=1.0, confidence=0.5, regime="trend"),
            _llm(action="proceed", confidence=0.9, regime="panic",
                 size_mult=2.0),
        )
        assert d["size"] == pytest.approx(2.0)
        # FULL replaces baseline conf + regime
        assert d["confidence"] == 0.9
        assert d["regime"] == "panic"

    def test_full_allows_size_up_to_2_5(self):
        d = apply_autonomy_mode(
            LLMMode.FULL,
            _baseline(size=1.0),
            _llm(action="proceed", size_mult=3.0),
        )
        assert d["size_multiplier"] == 2.5

    def test_flat_vetoes(self):
        d = apply_autonomy_mode(LLMMode.FULL, _baseline(),
                                _llm(action="flat"))
        assert d["action"] == "flat"
        assert d["llm_veto"] is True

    def test_flip_full_mode(self):
        d = apply_autonomy_mode(LLMMode.FULL,
                                _baseline(action="long"),
                                _llm(action="flip", confidence=0.6))
        # FULL mode has no soft gate
        assert d["action"] == "short"

    def test_strategy_weights_normalized(self):
        sw = StrategyWeights(regime_trend=2.0, monte_carlo_zones=2.0,
                             confidence_scorer=0.0, multi_tier_quality=0.0)
        llm = LLMDecision(
            action="proceed",
            confidence=0.8,
            regime="trend",
            strategy_weights=sw,
            memory_update=None,
            notes="",
            size_multiplier=1.0,
            entry_adjustment=None,
        )
        d = apply_autonomy_mode(LLMMode.FULL, _baseline(), llm)
        weights = d.get("strategy_weights", {})
        if weights:
            total = sum(v for v in weights.values() if isinstance(v, (int, float)))
            assert total == pytest.approx(1.0, rel=0.01)

    def test_none_llm_falls_back(self):
        d = apply_autonomy_mode(LLMMode.FULL, _baseline(), None)
        assert d["source"] == "baseline"
        assert d["llm_veto"] is False


# ── Helper predicates ────────────────────────────────────────


class TestHelpers:
    def test_get_mode_description_all(self):
        for mode in LLMMode:
            desc = get_mode_description(mode)
            assert isinstance(desc, str)
            assert len(desc) > 5

    def test_can_llm_flip(self):
        assert can_llm_flip(LLMMode.OFF) is False
        assert can_llm_flip(LLMMode.VETO_ONLY) is False
        assert can_llm_flip(LLMMode.SIZING) is False
        assert can_llm_flip(LLMMode.DIRECTION) is True
        assert can_llm_flip(LLMMode.FULL) is True

    def test_can_llm_scale_size(self):
        assert can_llm_scale_size(LLMMode.OFF) is False
        assert can_llm_scale_size(LLMMode.ADVISORY) is False
        assert can_llm_scale_size(LLMMode.VETO_ONLY) is False
        assert can_llm_scale_size(LLMMode.SIZING) is True
        assert can_llm_scale_size(LLMMode.DIRECTION) is True
        assert can_llm_scale_size(LLMMode.FULL) is True

    def test_is_llm_active(self):
        assert is_llm_active(LLMMode.OFF) is False
        assert is_llm_active(LLMMode.ADVISORY) is False
        assert is_llm_active(LLMMode.VETO_ONLY) is True
        assert is_llm_active(LLMMode.FULL) is True


class TestDivergenceStats:
    def setup_method(self):
        _divergence_history.clear()

    def test_empty_rate(self):
        # Less than 5 samples returns 0
        assert get_divergence_rate() == 0.0

    def test_empty_stats(self):
        stats = get_divergence_stats()
        assert stats["total"] == 0
        assert stats["divergence_rate"] == 0.0
