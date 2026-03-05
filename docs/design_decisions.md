Design decisions / preferences:
- Prefer explicit, verbose logging over cleverness.
- Prefer small, single-responsibility modules (one concern per file).
- Prefer config-driven behavior (no hardcoded thresholds).
- Prefer safe defaults: veto or downgrade instead of forcing execution.
- Prefer deterministic, testable pure logic separated from I/O and integrations.
- Prefer clear naming that matches the brief (snapshot_entry, live_entry, etc.).
