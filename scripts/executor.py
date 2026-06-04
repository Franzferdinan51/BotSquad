#!/usr/bin/env python
"""
Executor — carries out AUTO_FIX decisions from the Brain.

Reads ~/AgentShared/decisions/ for any new AUTO_FIX decisions, executes them,
updates the issue state, and reports results.

Safety:
- Only runs actions marked auto_execute=True
- Has a 5-minute cooldown per issue type to prevent loops
- Logs every action to logs/executor.log

Usage:
    python executor.py             # process all pending AUTO_FIX
    python executor.py --dry-run   # show what it would do
"""
import json
import subprocess
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

AGENT_HOME = Path.home() / "AgentShared"
DECISIONS = AGENT_HOME / "decisions"
STATE = AGENT_HOME / "state"
LOGS = AGENT_HOME / "logs"
DECISIONS.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

# Cooldown from config
sys.path.insert(0, str(Path(__file__).parent))
from config_loader import config
COOLDOWN_MINUTES = config["schedule"]["auto_fix_cooldown_minutes"]

# Cooldown per issue type to prevent fix-loops (set above from config)
cooldown_state_file = STATE / "executor_cooldowns.json"


def log(msg):
    ts = datetime.now().isoformat()
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOGS / "executor.log", "a") as f:
        f.write(line + "\n")


def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def load_cooldowns():
    if cooldown_state_file.exists():
        try:
            with open(cooldown_state_file) as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_cooldowns(state):
    with open(cooldown_state_file, "w") as f:
        json.dump(state, f, indent=2)


def in_cooldown(issue_type, cooldowns):
    if issue_type not in cooldowns:
        return False
    last = datetime.fromisoformat(cooldowns[issue_type])
    return datetime.now() - last < timedelta(minutes=COOLDOWN_MINUTES)


def restart_alpha_miner():
    """Restart the alpha-miner container."""
    launcher = Path.home() / "Desktop" / "alpha-miner-start.cmd"
    if not launcher.exists():
        return False, f"launcher not found: {launcher}"

    # First try a quick restart via docker
    rc, out, err = run("docker rm -f alpha-miner 2>&1")
    log(f"  docker rm: rc={rc} {out[:200]}")

    # Run the launcher
    rc, out, err = run(f'cmd.exe /c "{launcher}" 2>&1', timeout=60)
    return rc == 0, f"launcher rc={rc}\nstdout: {out[:300]}\nstderr: {err[:300]}"


def unload_lm_studio():
    """Unload all models from LM Studio to free VRAM."""
    cred_path = Path.home() / ".lmstudio" / "credentials" / "lmstudio-hub.json"
    if not cred_path.exists():
        return False, "no credentials"
    try:
        with open(cred_path) as f:
            creds = json.load(f)
        key = creds.get("key", "")
        token = key.get("keyId", "") if isinstance(key, dict) else key
        if not token:
            return False, "no token"
        # Use lms CLI to unload all
        rc, out, err = run("lms unload --all 2>&1", timeout=30)
        return rc == 0, f"lms unload rc={rc}\n{out[:200]}"
    except Exception as e:
        return False, str(e)


# Action registry — maps issue_type -> (function, args)
ACTION_REGISTRY = {
    "miner_down": (restart_alpha_miner, ()),
    "lm_studio_loaded": (unload_lm_studio, ()),
}


def get_pending_fixes(cooldowns):
    """Find AUTO_FIX decisions that haven't been executed yet (or are past cooldown)."""
    pending = []
    for f in sorted(DECISIONS.glob("*.json")):
        try:
            with open(f) as fh:
                d = json.load(fh)
        except:
            continue
        if d.get("decision") != "AUTO_FIX":
            continue
        if not d.get("auto_execute"):
            continue
        # Skip if already executed
        if d.get("executed"):
            continue
        issue_type = d["issue"].get("type", "")
        if not in_cooldown(issue_type, cooldowns):
            pending.append((f, d))
    return pending


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cooldowns = load_cooldowns()
    pending = get_pending_fixes(cooldowns)

    if not pending:
        log("No pending auto-fixes.")
        return 0

    log(f"Found {len(pending)} pending auto-fix(es)")
    results = []
    for fpath, decision in pending:
        issue_type = decision["issue"].get("type", "unknown")
        if issue_type not in ACTION_REGISTRY:
            log(f"  ⚠️ No handler for {issue_type} — skipping")
            continue
        fn, fn_args = ACTION_REGISTRY[issue_type]
        log(f"  → Executing fix for {issue_type}...")
        if args.dry_run:
            log(f"    (dry-run, would call {fn.__name__})")
            continue
        try:
            success, msg = fn(*fn_args)
            log(f"    {'✅' if success else '❌'} {fn.__name__}: {msg[:200]}")
            # Mark decision as executed
            decision["executed"] = True
            decision["executed_at"] = datetime.now().isoformat()
            decision["execution_result"] = {"success": success, "message": msg[:500]}
            with open(fpath, "w") as fh:
                json.dump(decision, fh, indent=2)
            # Update cooldown
            cooldowns[issue_type] = datetime.now().isoformat()
            results.append({"type": issue_type, "success": success})
        except Exception as e:
            log(f"    💥 Exception: {e}")
            results.append({"type": issue_type, "success": False, "error": str(e)})

    save_cooldowns(cooldowns)
    return 0 if all(r.get("success") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
