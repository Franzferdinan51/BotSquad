#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Orchestrator — runs the full Watcher → Brain → Executor loop.

This is the single entry point that gets scheduled (every 2h via Task Scheduler).
It runs:
  1. watcher.py  → collects state, detects issues, alerts Telegram
  2. brain.py    → reads issues, makes decisions, logs to decisions/
  3. executor.py → executes AUTO_FIX decisions

Each step is independent — if one fails, the next still runs.
Logs to logs/orchestrator.log.

Usage:
    python orchestrator.py            # full loop
    python orchestrator.py --watch    # watcher only
    python orchestrator.py --decide   # brain only
    python orchestrator.py --execute  # executor only
"""
import subprocess
import argparse
import sys
from pathlib import Path
from datetime import datetime

SCRIPTS = Path.home() / "AgentShared" / "scripts"
LOGS = Path.home() / "AgentShared" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)


def log(msg):
    ts = datetime.now().isoformat()
    line = f"[{ts}] {msg}"
    safe = line.encode("ascii", "replace").decode("ascii")
    print(safe)
    with open(LOGS / "orchestrator.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_step(name, script, args=None, timeout=300):
    """Run a script, return (success, output)."""
    cmd = [sys.executable, str(SCRIPTS / script)]
    if args:
        cmd.extend(args)
    log(f"--- {name} ---")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        success = r.returncode == 0
        log(f"  rc={r.returncode}")
        if r.stdout:
            log(f"  stdout: {r.stdout[:500]}")
        if r.stderr:
            log(f"  stderr: {r.stderr[:500]}")
        return success, r.stdout
    except subprocess.TimeoutExpired:
        log(f"  TIMEOUT after {timeout}s")
        return False, ""
    except Exception as e:
        log(f"  EXCEPTION: {e}")
        return False, ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="watcher only")
    parser.add_argument("--decide", action="store_true", help="brain only")
    parser.add_argument("--execute", action="store_true", help="executor only")
    args = parser.parse_args()

    # If no flag, run all
    run_all = not (args.watch or args.decide or args.execute)

    log("=== Orchestrator run started ===")
    results = {}

    if run_all or args.watch:
        ok, out = run_step("WATCHER", "watcher.py")
        results["watcher"] = ok

    if run_all or args.decide:
        ok, out = run_step("BRAIN", "brain.py")
        results["brain"] = ok

    if run_all or args.execute:
        ok, out = run_step("EXECUTOR", "executor.py")
        results["executor"] = ok

    log(f"=== Orchestrator done: {results} ===")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
