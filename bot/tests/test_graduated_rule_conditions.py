"""
Integration tests for GraduatedRulesEngine condition matching.

Audit finding (Run82, conf=88%): rules with symbol+side+confidence_min conditions
show times_applied=0 despite seemingly qualifying signals. This test suite verifies
the condition match path works end-to-end, catching any regression in rule loading
or condition evaluation.
"""

import json
import os
import tempfile
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm.graduated_rules import GraduatedRule, GraduatedRulesEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine(rules: list) -> GraduatedRulesEngine:
    """Build an engine pre-loaded with the given rule dicts.

    Overrides _save() to be a no-op so tests never write to the production
    data/llm/graduated_rules.json file via the engine's relative-path save.
    """
    engine = GraduatedRulesEngine()
    engine._rules = [GraduatedRule(**{k: v for k, v in r.items()
                                      if k in {f.name for f in __import__('dataclasses').fields(GraduatedRule)}})
                     for r in rules]
    engine._loaded = True
    engine._save = lambda: None  # prevent writes to production file
    return engine


# ---------------------------------------------------------------------------
# Rule.matches() unit tests
# ---------------------------------------------------------------------------

class TestGraduatedRuleMatches:
    def test_confidence_min_passes(self):
        rule = GraduatedRule(rule_id="r1", action="penalize",
                             conditions={"confidence_min": 70.0}, active=True)
        assert rule.matches(confidence=75.0)

    def test_confidence_min_blocks(self):
        rule = GraduatedRule(rule_id="r1", action="penalize",
                             conditions={"confidence_min": 70.0}, active=True)
        assert not rule.matches(confidence=65.0)

    def test_confidence_max_passes(self):
        rule = GraduatedRule(rule_id="r1", action="penalize",
                             conditions={"confidence_max": 80.0}, active=True)
        assert rule.matches(confidence=79.9)

    def test_confidence_max_blocks(self):
        # Engine uses strict > so confidence_max=80.0 still matches at exactly 80.0
        rule = GraduatedRule(rule_id="r1", action="penalize",
                             conditions={"confidence_max": 80.0}, active=True)
        assert not rule.matches(confidence=80.1)

    def test_confidence_band_passes(self):
        rule = GraduatedRule(rule_id="r1", action="penalize",
                             conditions={"confidence_min": 70.0, "confidence_max": 80.0},
                             active=True)
        assert rule.matches(confidence=75.0)

    def test_confidence_band_blocks_below(self):
        rule = GraduatedRule(rule_id="r1", action="penalize",
                             conditions={"confidence_min": 70.0, "confidence_max": 80.0},
                             active=True)
        assert not rule.matches(confidence=69.9)

    def test_confidence_band_blocks_above(self):
        rule = GraduatedRule(rule_id="r1", action="penalize",
                             conditions={"confidence_min": 70.0, "confidence_max": 80.0},
                             active=True)
        assert not rule.matches(confidence=80.1)

    def test_symbol_case_insensitive(self):
        rule = GraduatedRule(rule_id="r1", action="penalize",
                             conditions={"symbol": "BTC"}, active=True)
        assert rule.matches(symbol="btc")
        assert rule.matches(symbol="BTC")

    def test_symbol_mismatch_blocks(self):
        rule = GraduatedRule(rule_id="r1", action="penalize",
                             conditions={"symbol": "BTC"}, active=True)
        assert not rule.matches(symbol="ETH")

    def test_side_case_insensitive(self):
        rule = GraduatedRule(rule_id="r1", action="penalize",
                             conditions={"side": "SELL"}, active=True)
        assert rule.matches(side="sell")
        assert rule.matches(side="SELL")

    def test_side_mismatch_blocks(self):
        rule = GraduatedRule(rule_id="r1", action="penalize",
                             conditions={"side": "SELL"}, active=True)
        assert not rule.matches(side="BUY")

    def test_inactive_rule_never_matches(self):
        rule = GraduatedRule(rule_id="r1", action="penalize",
                             conditions={"symbol": "BTC"}, active=False)
        assert not rule.matches(symbol="BTC")

    def test_full_condition_btc_short_conf70_80(self):
        """Reproduces the exact condition of btc_short_conf70_80_penalize_v1."""
        rule = GraduatedRule(
            rule_id="btc_short_conf70_80_penalize_v1",
            action="penalize",
            conditions={"symbol": "BTC", "side": "SELL",
                        "confidence_min": 70.0, "confidence_max": 80.0},
            adjustment=-10.0, active=True,
        )
        # Should match
        assert rule.matches(symbol="BTC", side="SELL", confidence=75.0)
        # Should not match — wrong symbol
        assert not rule.matches(symbol="ETH", side="SELL", confidence=75.0)
        # Should not match — wrong side
        assert not rule.matches(symbol="BTC", side="BUY", confidence=75.0)
        # Should not match — confidence out of range
        assert not rule.matches(symbol="BTC", side="SELL", confidence=65.0)
        # Engine uses strict > for confidence_max, so 80.1 blocks but 80.0 still matches
        assert not rule.matches(symbol="BTC", side="SELL", confidence=80.1)


# ---------------------------------------------------------------------------
# GraduatedRulesEngine.evaluate_signal() integration tests
# ---------------------------------------------------------------------------

class TestEvaluateSignal:
    def test_penalize_rule_fires_and_reduces_confidence(self):
        engine = _make_engine([{
            "rule_id": "test_pen", "hypothesis_statement": "test penalty",
            "action": "penalize", "conditions": {"symbol": "BTC", "side": "SELL",
                                                  "confidence_min": 70.0, "confidence_max": 80.0},
            "adjustment": -10.0, "active": True, "confidence": 0.9,
            "times_applied": 0, "times_correct": 0,
        }])
        vetoed, adj_conf, summary = engine.evaluate_signal(
            symbol="BTC", side="SELL", confidence=75.0)
        assert not vetoed
        assert adj_conf == 65.0
        assert engine._rules[0].times_applied == 1

    def test_penalize_rule_does_not_fire_for_wrong_symbol(self):
        engine = _make_engine([{
            "rule_id": "test_pen", "hypothesis_statement": "test",
            "action": "penalize", "conditions": {"symbol": "BTC"},
            "adjustment": -10.0, "active": True, "confidence": 0.9,
            "times_applied": 0, "times_correct": 0,
        }])
        vetoed, adj_conf, summary = engine.evaluate_signal(symbol="ETH", confidence=75.0)
        assert not vetoed
        assert adj_conf == 75.0
        assert engine._rules[0].times_applied == 0

    def test_veto_rule_fires(self):
        engine = _make_engine([{
            "rule_id": "test_veto", "hypothesis_statement": "veto test",
            "action": "veto", "conditions": {"symbol": "HYPE", "side": "SELL"},
            "adjustment": 0.0, "active": True, "confidence": 0.95,
            "times_applied": 0, "times_correct": 0,
        }])
        vetoed, _, _ = engine.evaluate_signal(symbol="HYPE", side="SELL", confidence=80.0)
        assert vetoed

    def test_boost_rule_fires(self):
        engine = _make_engine([{
            "rule_id": "test_boost", "hypothesis_statement": "boost test",
            "action": "boost", "conditions": {"symbol": "ETH"},
            "adjustment": 8.0, "active": True, "confidence": 0.85,
            "times_applied": 0, "times_correct": 0,
        }])
        _, adj_conf, _ = engine.evaluate_signal(symbol="ETH", confidence=70.0)
        assert adj_conf == 78.0

    def test_inactive_rule_does_not_fire(self):
        engine = _make_engine([{
            "rule_id": "test_inactive", "hypothesis_statement": "inactive",
            "action": "penalize", "conditions": {"symbol": "BTC"},
            "adjustment": -15.0, "active": False, "confidence": 0.9,
            "times_applied": 0, "times_correct": 0,
        }])
        _, adj_conf, _ = engine.evaluate_signal(symbol="BTC", confidence=75.0)
        assert adj_conf == 75.0

    def test_confidence_clamps_to_zero_minimum(self):
        engine = _make_engine([{
            "rule_id": "test_clamp", "hypothesis_statement": "clamp",
            "action": "penalize", "conditions": {},
            "adjustment": -50.0, "active": True, "confidence": 0.9,
            "times_applied": 0, "times_correct": 0,
        }])
        _, adj_conf, _ = engine.evaluate_signal(confidence=30.0)
        assert adj_conf == 0.0

    def test_get_last_fired_rule_ids(self):
        engine = _make_engine([{
            "rule_id": "rule_abc", "hypothesis_statement": "test",
            "action": "penalize", "conditions": {"symbol": "SOL"},
            "adjustment": -5.0, "active": True, "confidence": 0.8,
            "times_applied": 0, "times_correct": 0,
        }])
        engine.evaluate_signal(symbol="SOL", confidence=70.0)
        assert "rule_abc" in engine.get_last_fired_rule_ids()


# ---------------------------------------------------------------------------
# Live rules file smoke test
# ---------------------------------------------------------------------------

class TestLiveRulesFile:
    LLM_RULES_PATH = os.path.join(
        os.path.dirname(__file__), "..", "data", "llm", "graduated_rules.json"
    )

    def test_rules_file_loads(self):
        assert os.path.exists(self.LLM_RULES_PATH), "graduated_rules.json missing"
        with open(self.LLM_RULES_PATH) as f:
            d = json.load(f)
        rules = d if isinstance(d, list) else d.get("rules", [])
        assert len(rules) > 0

    def _load_llm_rules(self):
        with open(self.LLM_RULES_PATH) as f:
            d = json.load(f)
        return d.get("rules", d) if isinstance(d, dict) else d

    def test_btc_short_conf70_80_rule_structure(self):
        rules = self._load_llm_rules()
        rule = next((r for r in rules if r.get("rule_id") == "btc_short_conf70_80_penalize_v1"), None)
        assert rule is not None, "btc_short_conf70_80_penalize_v1 not found"
        assert rule["active"] is True
        conds = rule["conditions"]
        assert "confidence_min" in conds, f"Missing confidence_min in conditions: {conds}"
        assert "confidence_max" in conds, f"Missing confidence_max in conditions: {conds}"
        assert conds["symbol"] == "BTC"
        assert conds["side"] == "SELL"

    def test_btc_short_conf70_80_fires_via_engine(self):
        """Verify btc_short_conf70_80_penalize_v1 fires for BTC SELL 75% using live rules.

        Must pass hour_utc=12 (midday) to avoid triggering night_session_block_v1 (00-06 UTC).
        When hour_utc=-1 (default), hour conditions are skipped, causing the night veto to
        match all signals regardless of time — a known engine quirk documented by this test.
        """
        rules = self._load_llm_rules()
        engine = _make_engine(rules)
        vetoed, adj_conf, summary = engine.evaluate_signal(
            symbol="BTC", side="SELL", confidence=75.0, hour_utc=12
        )
        assert not vetoed, f"Unexpected veto: {summary}"
        # btc_short_conf70_80_penalize_v1 applies -10pt penalty (halved from -20 by Run85)
        assert adj_conf < 75.0, f"Expected penalty from btc_short_conf70_80_penalize_v1, got adj_conf={adj_conf}"

    def test_night_session_veto_rule_active(self):
        """Verify night_session_block_v1 is active (veto rule for 00-06 UTC)."""
        rules = self._load_llm_rules()
        rule = next((r for r in rules if r.get("rule_id") == "night_session_block_v1"), None)
        assert rule is not None, "night_session_block_v1 not found in LLM rules"
        assert rule["active"] is True
        assert rule["action"] == "veto"
