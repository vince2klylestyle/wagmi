Logging spec:
Every trade log MUST include at least:
- snapshot_entry
- live_entry
- effective_entry
- snapshot_timestamp
- execution_timestamp
- snapshot_age_seconds
- slippage_pct
- spread_pct
- liquidity
- human_copy_tradable
- stale
- outcome
- state_path
- any veto/downgrade reasons
Logs must be machine-readable (CSV/JSONL) and consistent across modules.
