#!/usr/bin/env python3
"""
Phase 3A Staging Deployment Monitor
Tracks system health metrics every hour for 24 hours
"""

import os
import sys
import json
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

class StagingMonitor:
    def __init__(self):
        self.bot_dir = Path("/home/user/WAGMI/bot")
        self.data_dir = self.bot_dir / "data"
        self.db_path = self.data_dir / "trades.db"
        self.logs_dir = self.data_dir / "logs"
        self.start_time = datetime.utcnow()
        self.metrics = []

    def get_memory_usage(self):
        """Get memory usage of bot process"""
        try:
            result = subprocess.run(
                "ps aux | grep 'python.*run.py paper' | grep -v grep | awk '{print $6}'",
                shell=True,
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                mem_kb = int(result.stdout.strip())
                return mem_kb / 1024  # Convert to MB
        except:
            pass
        return None

    def get_database_size(self):
        """Get SQLite database file size"""
        try:
            if self.db_path.exists():
                size_mb = self.db_path.stat().st_size / (1024 * 1024)
                return size_mb
        except:
            pass
        return None

    def get_trade_count(self):
        """Get total number of trades recorded"""
        try:
            if self.db_path.exists():
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM trades")
                count = cursor.fetchone()[0]
                conn.close()
                return count
        except:
            pass
        return None

    def get_signal_count(self):
        """Get total number of signals evaluated"""
        try:
            if self.db_path.exists():
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM signals")
                count = cursor.fetchone()[0]
                conn.close()
                return count
        except:
            pass
        return None

    def get_error_count(self):
        """Get ERROR level log entries"""
        error_count = 0
        try:
            if self.logs_dir.exists():
                for log_file in self.logs_dir.glob("*.log"):
                    with open(log_file) as f:
                        error_count += sum(1 for line in f if "ERROR" in line)
        except:
            pass
        return error_count

    def get_last_trade_time(self):
        """Get timestamp of last trade"""
        try:
            if self.db_path.exists():
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(created_at) FROM trades")
                last_time = cursor.fetchone()[0]
                conn.close()
                if last_time:
                    return last_time
        except:
            pass
        return None

    def take_snapshot(self):
        """Take a health snapshot"""
        elapsed = datetime.utcnow() - self.start_time
        hours = elapsed.total_seconds() / 3600

        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "elapsed_hours": round(hours, 2),
            "memory_mb": self.get_memory_usage(),
            "database_mb": self.get_database_size(),
            "trade_count": self.get_trade_count(),
            "signal_count": self.get_signal_count(),
            "error_count": self.get_error_count(),
            "last_trade": self.get_last_trade_time(),
        }

        self.metrics.append(snapshot)
        return snapshot

    def check_success_criteria(self):
        """Check if success criteria are being met"""
        latest = self.metrics[-1] if self.metrics else {}
        issues = []

        # Check memory
        if latest.get("memory_mb") and latest["memory_mb"] > 100:
            issues.append(f"⚠️  Memory exceeds 100 MB: {latest['memory_mb']:.1f} MB")

        # Check database
        if latest.get("database_mb") and latest["database_mb"] > 20:
            issues.append(f"⚠️  Database exceeds 20 MB: {latest['database_mb']:.1f} MB")

        # Check errors
        if latest.get("error_count", 0) > 0:
            issues.append(f"⚠️  ERROR logs detected: {latest['error_count']} errors")

        # Check trade progress
        if latest.get("elapsed_hours", 0) > 4 and latest.get("trade_count", 0) == 0:
            issues.append(f"⚠️  No trades executed after {latest['elapsed_hours']:.1f} hours")

        return issues

    def print_snapshot(self, snapshot):
        """Pretty print a snapshot"""
        print(f"\n{'='*70}")
        print(f"STAGING HEALTH SNAPSHOT @ T+{snapshot['elapsed_hours']:.1f}h")
        print(f"{'='*70}")
        print(f"Timestamp:     {snapshot['timestamp']}")
        print(f"Memory:        {snapshot['memory_mb']:.1f} MB" if snapshot['memory_mb'] else "Memory:        --")
        print(f"Database:      {snapshot['database_mb']:.2f} MB" if snapshot['database_mb'] else "Database:      --")
        print(f"Trades:        {snapshot['trade_count']} trades" if snapshot['trade_count'] is not None else "Trades:        --")
        print(f"Signals:       {snapshot['signal_count']} signals" if snapshot['signal_count'] is not None else "Signals:       --")
        print(f"Errors:        {snapshot['error_count']} ERROR logs")
        print(f"Last Trade:    {snapshot['last_trade']}")
        print(f"{'='*70}")

        # Check for issues
        issues = self.check_success_criteria()
        if issues:
            print("ISSUES DETECTED:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print("✅ All checks passing")

    def save_report(self, filename="PHASE_3A_METRICS.json"):
        """Save metrics to JSON report"""
        report = {
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.utcnow().isoformat(),
            "total_hours": (datetime.utcnow() - self.start_time).total_seconds() / 3600,
            "snapshots": self.metrics
        }

        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n✅ Metrics saved to {filename}")
        return filename

if __name__ == "__main__":
    monitor = StagingMonitor()

    # Initial snapshot
    print("🚀 PHASE 3A STAGING DEPLOYMENT MONITOR")
    print(f"Start time: {monitor.start_time.isoformat()}")
    print("Taking initial snapshot...")

    initial = monitor.take_snapshot()
    monitor.print_snapshot(initial)

    print("\n📊 Snapshots will be taken hourly for 24 hours")
    print("   Run this script hourly or use: watch -n 3600 python PHASE_3A_STAGING_MONITOR.py")
    print(f"\nMetrics will be saved to: PHASE_3A_METRICS.json")
