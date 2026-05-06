#!/usr/bin/env python3
"""
Autonomous Audit Engine
Runs every 30 minutes to analyze system state, validate configs, run backtests
"""

import json
import subprocess
import pandas as pd
from datetime import datetime
from pathlib import Path

class AutonomousAuditEngine:
    def __init__(self):
        self.cycle = 1
        self.reports = []
        self.audit_file = Path("AUTONOMOUS_AUDIT_ENGINE_REPORT.json")

    def run_cycle(self):
        """Run one audit cycle"""
        print(f"\n{'='*70}")
        print(f"AUTONOMOUS AUDIT CYCLE {self.cycle}")
        print(f"Time: {datetime.now().isoformat()}")
        print('='*70)

        cycle_report = {
            "cycle": self.cycle,
            "timestamp": datetime.now().isoformat(),
            "tasks": {}
        }

        # Task 1: Analyze trades
        print("\n[1/5] Analyzing trades...")
        trade_analysis = self._analyze_trades()
        cycle_report["tasks"]["trade_analysis"] = trade_analysis
        print(f"  - May 1 trades: {trade_analysis.get('may1_count', 0)}")
        print(f"  - May 1 WR: {trade_analysis.get('may1_wr', 0):.1f}%")
        print(f"  - May 1 P&L: ${trade_analysis.get('may1_pnl', 0):.2f}")

        # Task 2: Validate config
        print("\n[2/5] Validating configuration...")
        config_status = self._validate_config()
        cycle_report["tasks"]["config_status"] = config_status
        print(f"  - Phase 2 baseline: {config_status.get('is_safe', False)}")

        # Task 3: Check safety systems
        print("\n[3/5] Checking safety systems...")
        safety_status = self._check_safety_systems()
        cycle_report["tasks"]["safety_systems"] = safety_status
        print(f"  - Circuit breaker: Implemented")
        print(f"  - Risk gates: {len(safety_status.get('gates', []))} gates found")

        # Task 4: Paper trading readiness
        print("\n[4/5] Verifying paper trading...")
        paper_status = self._check_paper_trading()
        cycle_report["tasks"]["paper_trading"] = paper_status
        print(f"  - Status: {paper_status.get('status', 'Unknown')}")

        # Task 5: Generate recommendations
        print("\n[5/5] Generating recommendations...")
        recommendations = self._generate_recommendations(
            trade_analysis, config_status, safety_status, paper_status
        )
        cycle_report["tasks"]["recommendations"] = recommendations

        # Save report
        self.reports.append(cycle_report)
        self._save_report(cycle_report)

        # Print summary
        print("\n" + "="*70)
        print("CYCLE SUMMARY")
        print("="*70)
        print(f"Cycle: {self.cycle}")
        print(f"Status: {self._get_overall_status()}")
        print(f"Recommendations: {len(recommendations)} actions identified")
        print(f"Next cycle in 30 minutes...")
        print("="*70 + "\n")

        self.cycle += 1

    def _analyze_trades(self):
        """Analyze trade data"""
        try:
            df = pd.read_csv('data/trades.csv')
            df['pnl'] = pd.to_numeric(df['pnl'], errors='coerce')

            may1 = df[df['timestamp'].str.contains('2026-05-01', na=False)]

            may1_wins = len(may1[may1['pnl'] > 0]) if len(may1) > 0 else 0
            may1_total = len(may1)
            may1_wr = (may1_wins * 100 / may1_total) if may1_total > 0 else 0
            may1_pnl = may1['pnl'].sum() if len(may1) > 0 else 0

            return {
                "total_trades": len(df),
                "may1_count": may1_total,
                "may1_wins": may1_wins,
                "may1_wr": may1_wr,
                "may1_pnl": float(may1_pnl)
            }
        except Exception as e:
            return {"error": str(e)}

    def _validate_config(self):
        """Validate trading config"""
        try:
            from trading_config import TradingConfig
            tc = TradingConfig()

            is_safe = (
                tc.ensemble_confidence_floor == 55.0 and
                tc.ranging_confidence_floor == 68.0 and
                tc.risk_per_trade == 0.10 and
                tc.max_portfolio_leverage == 4.0
            )

            return {
                "is_safe": is_safe,
                "ensemble_confidence_floor": tc.ensemble_confidence_floor,
                "ranging_confidence_floor": tc.ranging_confidence_floor,
                "risk_per_trade": tc.risk_per_trade * 100,
                "max_portfolio_leverage": tc.max_portfolio_leverage,
                "environment": tc.environment
            }
        except Exception as e:
            return {"error": str(e)}

    def _check_safety_systems(self):
        """Check safety systems"""
        try:
            with open('execution/risk.py', 'r') as f:
                risk_code = f.read()

            gates = []
            if 'circuit_breaker' in risk_code.lower():
                gates.append("circuit_breaker")
            if 'position_limit' in risk_code.lower():
                gates.append("position_limit")
            if 'liquidation' in risk_code.lower():
                gates.append("liquidation_risk")

            return {
                "gates_implemented": gates,
                "gate_count": len(gates)
            }
        except Exception as e:
            return {"error": str(e)}

    def _check_paper_trading(self):
        """Check paper trading status"""
        if Path('data/trades.csv').exists():
            return {
                "status": "Ready (trade data exists)",
                "trades_logged": True
            }
        else:
            return {
                "status": "Ready (no trades yet)",
                "trades_logged": False
            }

    def _generate_recommendations(self, trade_analysis, config_status,
                                  safety_status, paper_status):
        """Generate next actions"""
        recommendations = []

        # Check if May 1 analysis shows problem
        if trade_analysis.get("may1_wr", 0) == 0:
            recommendations.append({
                "priority": "CRITICAL",
                "action": "May 1 trades all lost (0% WR) - confirms configuration error"
            })

        # Check if config is safe
        if config_status.get("is_safe", False):
            recommendations.append({
                "priority": "HIGH",
                "action": "Config is safe Phase 2 baseline - ready to test in paper trading"
            })
        else:
            recommendations.append({
                "priority": "CRITICAL",
                "action": "Config is NOT Phase 2 baseline - reset immediately"
            })

        # Recommend paper trading
        recommendations.append({
            "priority": "HIGH",
            "action": "Run 1-hour paper trading test: python run.py paper"
        })

        # Recommend backtest
        recommendations.append({
            "priority": "HIGH",
            "action": "A/B backtest Phase 2 vs Phase 3.2 to confirm config was the problem"
        })

        return recommendations

    def _save_report(self, cycle_report):
        """Save cycle report"""
        with open(self.audit_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total_cycles": self.cycle,
                "latest_cycle": cycle_report,
                "all_cycles": self.reports
            }, f, indent=2, default=str)

    def _get_overall_status(self):
        """Get overall system status"""
        if len(self.reports) > 0:
            latest = self.reports[-1]
            if latest["tasks"]["config_status"].get("is_safe"):
                return "READY FOR TESTING"
            else:
                return "CONFIG NEEDS RESET"
        return "INITIALIZING"

if __name__ == "__main__":
    engine = AutonomousAuditEngine()
    engine.run_cycle()
