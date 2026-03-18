"""
Backtest management API routes.

Safety contract:
- Existing backtest_results/*.json files are NEVER modified or deleted.
- New UI-triggered runs always use --fresh (no --learn, no --llm).
- New runs save to timestamped files only (never 'latest.json').
- Max 1 concurrent job; max 90 days lookback.
"""
import os
import re
import json
import glob
import uuid
import subprocess
import threading
from datetime import datetime
from typing import Dict, Optional, Any

from fastapi import APIRouter, Query, HTTPException

router = APIRouter(prefix="/v1/backtest", tags=["backtest"])

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BOT_ROOT = os.environ.get(
    "BOT_ROOT",
    os.path.join(os.path.dirname(__file__), "..", "..", "bot"),
)
_RESULTS_DIR = os.path.join(_BOT_ROOT, "backtest_results")
_PYTHON = os.environ.get("BOT_PYTHON", "python3")

# ---------------------------------------------------------------------------
# In-memory job store (process lifetime; restart clears it)
# ---------------------------------------------------------------------------
_jobs: Dict[str, dict] = {}  # job_id -> {status, output, error, result_file}
_active_job: Optional[str] = None  # only 1 concurrent job
_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Allowed symbols (whitelist for safety)
# ---------------------------------------------------------------------------
_ALLOWED_SYMBOLS = {"BTC", "ETH", "SOL", "HYPE", "LINK", "AVAX", "DOGE", "ARB", "OP", "INJ"}


def _sanitize_symbols(raw: str) -> str:
    """Return a comma-separated string of whitelisted uppercase symbols."""
    parts = [s.strip().upper() for s in raw.split(",") if s.strip()]
    valid = [s for s in parts if s in _ALLOWED_SYMBOLS and re.match(r'^[A-Z]{2,6}$', s)]
    if not valid:
        raise ValueError(f"No valid symbols. Allowed: {', '.join(sorted(_ALLOWED_SYMBOLS))}")
    return ",".join(valid)


def _list_result_files() -> list:
    """Return metadata for all *.json files in backtest_results/, newest first."""
    if not os.path.isdir(_RESULTS_DIR):
        return []
    files = glob.glob(os.path.join(_RESULTS_DIR, "*.json"))
    items = []
    for path in files:
        basename = os.path.basename(path)
        run_id = basename.replace(".json", "")
        try:
            stat = os.stat(path)
            mtime = datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z"
            size = stat.st_size
            # Quick-read just the config + top-level result summary (avoid loading huge files)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = data.get("config", {})
            res = data.get("results", {})
            items.append({
                "id": run_id,
                "file": basename,
                "created_at": mtime,
                "size_bytes": size,
                "symbols": cfg.get("symbols", []),
                "days": cfg.get("days"),
                "total_return_pct": res.get("total_return_pct"),
                "win_rate": res.get("win_rate"),
                "total_trades": res.get("total_trades"),
                "net_pnl": res.get("net_pnl"),
                "max_drawdown_pct": res.get("max_drawdown_pct"),
                "profit_factor": res.get("profit_factor"),
            })
        except Exception:
            items.append({"id": run_id, "file": basename, "created_at": mtime, "size_bytes": size})
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/results")
def list_backtest_results():
    """List all backtest result files with summary metadata."""
    items = _list_result_files()
    return {"results": items, "count": len(items)}


@router.get("/results/{run_id}")
def get_backtest_result(run_id: str):
    """
    Return full JSON for a single backtest run.
    run_id is the filename base (e.g. 'latest', 'backtest_20260313_052715').
    """
    # Sanitise run_id to prevent path traversal
    if not re.match(r'^[a-zA-Z0-9_\-]+$', run_id):
        raise HTTPException(status_code=400, detail="Invalid run_id")

    path = os.path.join(_RESULTS_DIR, f"{run_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Result '{run_id}' not found")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read result: {e}")


@router.post("/run")
def run_backtest(
    symbols: str = Query(default="BTC,SOL,HYPE", description="Comma-separated symbols"),
    days: int = Query(default=30, ge=7, le=90, description="Lookback days (7–90)"),
):
    """
    Trigger a new backtest run. Returns a job_id to poll for status.

    Safety: always runs with --fresh. Never uses --learn or --llm.
    Results saved to a NEW timestamped file; existing files never touched.
    Maximum 1 concurrent job.
    """
    global _active_job

    with _lock:
        # Check for active job
        if _active_job and _active_job in _jobs:
            job = _jobs[_active_job]
            if job.get("status") in ("pending", "running"):
                raise HTTPException(
                    status_code=429,
                    detail=f"A backtest is already running (job {_active_job}). Wait for it to finish.",
                )

        # Validate symbols
        try:
            clean_symbols = _sanitize_symbols(symbols)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        job_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        out_filename = f"backtest_ui_{timestamp}.json"
        out_path = os.path.join(_RESULTS_DIR, out_filename)

        _jobs[job_id] = {
            "status": "pending",
            "job_id": job_id,
            "symbols": clean_symbols,
            "days": days,
            "result_file": out_filename,
            "result_id": out_filename.replace(".json", ""),
            "started_at": datetime.utcnow().isoformat() + "Z",
            "finished_at": None,
            "error": None,
            "log_tail": [],
        }
        _active_job = job_id

    # Spawn thread so endpoint returns immediately
    def _run():
        global _active_job
        _jobs[job_id]["status"] = "running"
        os.makedirs(_RESULTS_DIR, exist_ok=True)

        cmd = [
            _PYTHON, "run.py", "backtest",
            "--symbols", clean_symbols,
            "--days", str(days),
            "--fresh",
            "--output", out_path,
        ]
        log_lines = []
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=_BOT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in proc.stdout:  # type: ignore
                clean = line.rstrip()
                log_lines.append(clean)
                # Keep last 50 lines for status polling
                _jobs[job_id]["log_tail"] = log_lines[-50:]
            proc.wait(timeout=600)  # 10-minute timeout

            if proc.returncode == 0:
                _jobs[job_id]["status"] = "done"
            else:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"] = f"Process exited with code {proc.returncode}"
        except Exception as e:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(e)
        finally:
            _jobs[job_id]["finished_at"] = datetime.utcnow().isoformat() + "Z"
            with _lock:
                if _active_job == job_id:
                    _active_job = None

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return {
        "job_id": job_id,
        "status": "pending",
        "symbols": clean_symbols,
        "days": days,
        "result_file": out_filename,
    }


@router.get("/status/{job_id}")
def get_backtest_status(job_id: str):
    """Poll the status of a running or completed backtest job."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    job = dict(_jobs[job_id])
    # If done, include result summary if file exists
    if job.get("status") == "done":
        result_path = os.path.join(_RESULTS_DIR, job.get("result_file", ""))
        if os.path.exists(result_path):
            try:
                with open(result_path, "r") as f:
                    data = json.load(f)
                job["result_summary"] = {
                    "total_return_pct": data.get("results", {}).get("total_return_pct"),
                    "win_rate": data.get("results", {}).get("win_rate"),
                    "total_trades": data.get("results", {}).get("total_trades"),
                    "net_pnl": data.get("results", {}).get("net_pnl"),
                }
            except Exception:
                pass
    return job
