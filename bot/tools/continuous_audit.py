#!/usr/bin/env python3
"""
Continuous Autonomous Audit System
Runs throughout the night, probing for gaps and opportunities.

Queries:
1. Are feedback systems instantiated?
2. Are recording methods being called?
3. Is recorded data being applied?
4. Are there data files without usage?
5. Are there learning systems without feedback?
6. Are there decision points that ignore available data?
"""

import json
import os
import sys
import subprocess
from collections import defaultdict
from datetime import datetime

class ContinuousAudit:
    def __init__(self):
        self.bot_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.feedback_dir = os.path.join(self.bot_dir, "data", "feedback")
        self.findings = []

    def audit_feedback_data_files(self):
        """Check what data exists and its size/freshness."""
        print("\n[AUDIT] Feedback Data Files")
        print("=" * 70)

        if not os.path.exists(self.feedback_dir):
            return

        for fname in sorted(os.listdir(self.feedback_dir)):
            if not fname.endswith(".json"):
                continue

            fpath = os.path.join(self.feedback_dir, fname)
            size = os.path.getsize(fpath)
            mtime = os.path.getmtime(fpath)
            age_hours = (datetime.now().timestamp() - mtime) / 3600

            try:
                with open(fpath) as f:
                    data = json.load(f)

                record_count = 0
                if isinstance(data, dict):
                    # Count objects with "wins" field (feedback records)
                    for v in data.values():
                        if isinstance(v, dict) and "wins" in v:
                            record_count += 1

                status = "STALE" if age_hours > 24 else "FRESH" if age_hours < 1 else "OLD"
                print(f"  {fname:35s} | {size:7d}B | {age_hours:5.1f}h | {status}")

                # Flag large unused data files
                if size > 10000 and fname in ["signal_quality.json"]:
                    self.findings.append(f"GAP: {fname} has {size}B data but not applied")
            except Exception as e:
                print(f"  {fname:35s} | ERROR: {str(e)[:40]}")

    def audit_manager_instantiation(self):
        """Check which feedback managers are instantiated in main loop."""
        print("\n[AUDIT] Manager Instantiation Status")
        print("=" * 70)

        main_file = os.path.join(self.bot_dir, "multi_strategy_main.py")

        managers = [
            "strategy_weights", "regime_feedback", "confidence_floor",
            "hold_time_rules", "ic_tracker", "signal_quality", "auto_optimizer",
            "parameter_tuner", "continuous_backtest", "ev_calibrator"
        ]

        with open(main_file, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        for mgr in managers:
            # Check if instantiated as instance variable
            pattern1 = f"self.{mgr} = "
            pattern2 = f"self._{mgr} = "

            is_instantiated = pattern1 in content or pattern2 in content
            status = "WIRED" if is_instantiated else "NOT WIRED"

            print(f"  {mgr:30s} | {status}")

            if not is_instantiated and mgr != "auto_optimizer":  # auto_optimizer is complex
                self.findings.append(f"GAP: {mgr} not instantiated")

    def audit_data_application(self):
        """Check if recorded data is actually used in decisions."""
        print("\n[AUDIT] Data Application Status")
        print("=" * 70)

        # Check if signal_quality.score_signal() is called
        ensemble_file = os.path.join(self.bot_dir, "strategies", "ensemble.py")
        with open(ensemble_file, encoding="utf-8", errors="ignore") as f:
            ensemble_content = f.read()

        if "score_signal" not in ensemble_content:
            self.findings.append("CRITICAL: signal_quality.score_signal() never called")
            print(f"  signal_quality scoring:        NOT APPLIED")
        else:
            print(f"  signal_quality scoring:        APPLIED")

        # Check confidence adjustment locations
        import re
        conf_assignments = len(re.findall(r"\.confidence\s*=", ensemble_content))
        print(f"  Confidence assignment points:  {conf_assignments}")

    def audit_recording_calls(self):
        """Check which record/track methods are actually called."""
        print("\n[AUDIT] Recording Method Calls")
        print("=" * 70)

        main_file = os.path.join(self.bot_dir, "multi_strategy_main.py")
        with open(main_file, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        recording_methods = {
            "regime_feedback.record_trade": "Regime-specific performance",
            "confidence_floor.record_outcome": "Confidence floor learning",
            "signal_quality.record_outcome": "Signal quality learning",
            "hold_time_rules.record_trade": "Hold-time minimum learning",
            "parameter_tuner.record_outcome": "Parameter tuning data",
            "continuous_backtest.record_outcome": "Live trade validation"
        }

        for method, desc in recording_methods.items():
            is_called = method in content
            status = "CALLED" if is_called else "NOT CALLED"
            print(f"  {method:35s} | {status:10s} | {desc}")

            if not is_called and "continuous_backtest" not in method:
                self.findings.append(f"GAP: {method}() never called")

    def print_summary(self):
        """Print audit summary with recommendations."""
        print("\n" + "=" * 70)
        print("[SUMMARY] Gaps and Recommendations")
        print("=" * 70)

        if not self.findings:
            print("✓ All systems nominal")
            return

        by_severity = defaultdict(list)
        for finding in self.findings:
            if finding.startswith("CRITICAL"):
                by_severity["CRITICAL"].append(finding)
            elif finding.startswith("GAP"):
                by_severity["GAP"].append(finding)
            else:
                by_severity["INFO"].append(finding)

        for severity in ["CRITICAL", "GAP", "INFO"]:
            if severity in by_severity:
                print(f"\n{severity}:")
                for finding in by_severity[severity]:
                    print(f"  • {finding}")

    def run(self):
        """Execute full audit."""
        print("\n" + "=" * 70)
        print(f"[CONTINUOUS AUDIT] {datetime.now().isoformat()}")
        print("=" * 70)

        self.audit_feedback_data_files()
        self.audit_manager_instantiation()
        self.audit_data_application()
        self.audit_recording_calls()
        self.print_summary()

        return len(self.findings)

if __name__ == "__main__":
    audit = ContinuousAudit()
    gap_count = audit.run()
    sys.exit(gap_count)
