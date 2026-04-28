#!/usr/bin/env python3
"""
Smoking gun: prove the CLI network works after the structured_output fix (§22.7).
Run this AFTER applying the §22.4 fix to bot/llm/claude_cli_client.py.
"""
import json
import sys

sys.path.insert(0, '/c/Users/vince/WAGMI PROJECT/WAGMI')

try:
    from bot.llm.claude_cli_client import call_agent
    from bot.llm.agents.prompts import AGENT_PROMPTS
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    print("Make sure you're running this from the WAGMI directory")
    sys.exit(1)

# Use actual regime schema from the codebase
REGIME_SCHEMA = {
    "type": "object",
    "properties": {
        "regime": {
            "type": "string",
            "enum": ["trending_bull", "trending_bear", "range", "high_volatility", "low_liquidity", "news_dislocation", "unknown"]
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "bias": {"type": "string", "enum": ["long", "neutral", "short"]},
        "vol_band": {"type": "string"},
        "narrative": {"type": "string"}
    },
    "required": ["regime", "confidence", "bias", "vol_band", "narrative"]
}

REGIME_SYSTEM = "You are a market regime classifier. Analyze market data and return your assessment as JSON."

REGIME_INPUT = """BTC at $75,888. 24h change: +3.2%, 1h RSI: 61 (neutral), above EMA20 (+3.8%),
volatility: 1.5× baseline, funding rate: +0.015%, OI: flat, 4h ADX: 28 (trending).
Recent news: positive sentiment. Classify the regime."""

def test_model(model: str) -> bool:
    """Test if the model returns valid JSON via CLI."""
    print(f"\n{'='*60}")
    print(f"Testing: {model.upper()}")
    print(f"{'='*60}")

    try:
        r = call_agent(
            input_text=REGIME_INPUT,
            system_prompt=REGIME_SYSTEM,
            model=model,
            json_schema=REGIME_SCHEMA,
            timeout=60
        )

        print(f"✓ Call succeeded")
        print(f"  - OK: {r.ok}")
        print(f"  - Latency: {r.latency_s:.2f}s")
        print(f"  - Cost: ${r.cost_usd:.4f}")
        print(f"  - Text length: {len(r.text)} chars")

        if len(r.text) > 0:
            print(f"  - Text preview: {r.text[:100]!r}...")

        if r.parsed:
            required = {"regime", "confidence", "bias", "vol_band", "narrative"}
            missing = required - set(r.parsed.keys())

            print(f"✓ JSON parsed successfully")
            print(f"  - Keys found: {sorted(r.parsed.keys())}")

            if missing:
                print(f"✗ MISSING required fields: {missing}")
                return False

            print(f"\n  Parsed output:")
            for key, val in r.parsed.items():
                if key == "narrative":
                    print(f"    - {key}: {str(val)[:60]}...")
                else:
                    print(f"    - {key}: {val}")

            return True
        else:
            print(f"✗ JSON parsing FAILED — parsed is None")
            print(f"  - This indicates the §22.4 fix may not be applied correctly")
            return False

    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("§22.7 CLI Structured Output Reproducer")
    print("Verifying the §22.4 fix resolves JSON parsing on CLI network")
    print("="*60)

    haiku_ok = test_model("haiku")
    sonnet_ok = test_model("sonnet")

    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Haiku:  {'✓ PASS' if haiku_ok else '✗ FAIL'}")
    print(f"Sonnet: {'✓ PASS' if sonnet_ok else '✗ FAIL'}")

    if haiku_ok and sonnet_ok:
        print(f"\n✓ All tests PASSED! The §22.4 fix is working.")
        print(f"  Regime Agent will now correctly parse JSON from Haiku.")
        print(f"  100% VETO loop is RESOLVED.")
        sys.exit(0)
    else:
        print(f"\n✗ Tests FAILED! The fix may not be complete.")
        print(f"  Check that bot/llm/claude_cli_client.py:139-145 has:")
        print(f"    - Check for structured_output field")
        print(f"    - JSON-serialize if dict")
        print(f"    - Fallback to result/text fields")
        sys.exit(1)
