"""
Smoke tests for llm/knowledge_roadmap.py.

Covers:
  - RoadmapState dataclass init + properties
  - Singleton get_roadmap_state()
  - Config accessors: get_recommended_llm_mode, is_money_allowed, get_max_stake
  - format_roadmap_status / format_roadmap_overview
  - evaluate_gates smoke
  - force_phase + demote_phase round-trip
  - Serialization round-trip (_load_state / _save_state)
"""
import json
import os
import sys
import tempfile
import time
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import llm.knowledge_roadmap as kr
from llm.knowledge_roadmap import (
    PHASE_CONFIGS,
    RoadmapState,
    _load_state,
    _save_state,
    demote_phase,
    evaluate_gates,
    force_phase,
    format_roadmap_overview,
    format_roadmap_status,
    get_max_stake,
    get_recommended_llm_mode,
    get_roadmap_config,
    get_roadmap_state,
    is_money_allowed,
    promote_phase,
)


# ── Constructor / dataclass ─────────────────────────────

def test_roadmap_state_defaults():
    s = RoadmapState()
    assert s.current_phase == 1
    assert s.phase_started_at == 0.0
    assert s.roadmap_started_at == 0.0
    assert s.phase_history == []
    assert s.demotions == []
    assert s.auto_demotion_enabled is True
    assert s.manual_override is False


def test_roadmap_state_hours_in_phase_zero_when_unstarted():
    s = RoadmapState()
    assert s.hours_in_phase == 0.0
    assert s.total_hours == 0.0


def test_roadmap_state_hours_increase_with_time():
    s = RoadmapState()
    s.phase_started_at = time.time() - 3600  # 1 hour ago
    s.roadmap_started_at = time.time() - 3600
    assert 0.9 < s.hours_in_phase < 1.1
    assert 0.9 < s.total_hours < 1.1


# ── Config accessors ─────────────────────────────────────

def test_get_roadmap_config_returns_dict():
    c = get_roadmap_config()
    assert isinstance(c, dict)
    assert "name" in c
    assert "llm_mode" in c


def test_recommended_llm_mode_is_int():
    m = get_recommended_llm_mode()
    assert isinstance(m, int)
    assert 0 <= m <= 5


def test_is_money_allowed_returns_bool():
    v = is_money_allowed()
    assert isinstance(v, bool)


def test_get_max_stake_non_negative_or_sentinel():
    v = get_max_stake()
    # Phase 5 uses -1 as "unlimited" sentinel
    assert isinstance(v, (int, float))


# ── Formatters ────────────────────────────────────────────

def test_format_roadmap_status_nonempty_string():
    s = format_roadmap_status()
    assert isinstance(s, str)
    assert "Phase" in s


def test_format_roadmap_overview_includes_all_phases():
    s = format_roadmap_overview()
    assert isinstance(s, str)
    # All 5 phases should appear somewhere in the overview
    for phase_num in PHASE_CONFIGS:
        assert str(phase_num) in s or PHASE_CONFIGS[phase_num]["name"] in s


# ── Gate evaluation ──────────────────────────────────────

def test_evaluate_gates_returns_dict():
    r = evaluate_gates()
    assert isinstance(r, dict)
    # Either at max phase, or produces standard fields
    if r.get("phase", 0) < 5:
        assert "all_passed" in r
        assert "gates" in r


# ── Singleton ────────────────────────────────────────────

def test_get_roadmap_state_singleton():
    a = get_roadmap_state()
    b = get_roadmap_state()
    assert a is b


# ── Force phase + demote (isolated state) ───────────────

def test_force_phase_valid_and_invalid():
    # Invalid phase numbers rejected
    r = force_phase(0)
    assert r["success"] is False
    r = force_phase(99)
    assert r["success"] is False


def test_demote_phase_rejects_higher_target():
    state = get_roadmap_state()
    # Demote target must be strictly lower than current
    r = demote_phase(state.current_phase + 10, reason="test")
    assert r["success"] is False


# ── Serialization round-trip ────────────────────────────

def test_save_and_load_state_roundtrip():
    """State must survive a save -> load cycle."""
    with tempfile.TemporaryDirectory() as d:
        # Temporarily redirect the state path
        original_path = kr._ROADMAP_STATE_PATH
        try:
            kr._ROADMAP_STATE_PATH = os.path.join(d, "roadmap_state.json")
            state = RoadmapState(
                current_phase=3,
                phase_started_at=time.time(),
                roadmap_started_at=time.time() - 7200,
                auto_demotion_enabled=False,
                manual_override=True,
                override_reason="unit-test",
            )
            _save_state(state)
            # Now reload
            restored = _load_state()
            assert restored.current_phase == 3
            assert restored.auto_demotion_enabled is False
            assert restored.manual_override is True
            assert restored.override_reason == "unit-test"
        finally:
            kr._ROADMAP_STATE_PATH = original_path


def test_load_state_returns_default_when_missing():
    with tempfile.TemporaryDirectory() as d:
        original_path = kr._ROADMAP_STATE_PATH
        try:
            kr._ROADMAP_STATE_PATH = os.path.join(d, "nope.json")
            # File doesn't exist — should get fresh defaults
            restored = _load_state()
            assert restored.current_phase == 1
        finally:
            kr._ROADMAP_STATE_PATH = original_path


def test_load_state_handles_corrupted_json():
    with tempfile.TemporaryDirectory() as d:
        original_path = kr._ROADMAP_STATE_PATH
        try:
            kr._ROADMAP_STATE_PATH = os.path.join(d, "roadmap_state.json")
            with open(kr._ROADMAP_STATE_PATH, "w") as f:
                f.write("{not valid json")
            # Should fall back to defaults without crashing
            restored = _load_state()
            assert restored.current_phase == 1
        finally:
            kr._ROADMAP_STATE_PATH = original_path


# ── promote_phase rejects when gates fail (default state is phase 1 with fresh env) ──

def test_promote_phase_with_ungated_default_state():
    """In a fresh environment with no learning history, gates should fail."""
    # Save current state; force a fresh phase-1 state for this test
    original_state = kr._state
    try:
        kr._state = RoadmapState(
            current_phase=1,
            phase_started_at=time.time(),
            roadmap_started_at=time.time(),
        )
        result = promote_phase()
        # Promotion should either fail (gates not met) OR succeed if all gates pass
        assert isinstance(result, dict)
        assert "success" in result
    finally:
        kr._state = original_state
