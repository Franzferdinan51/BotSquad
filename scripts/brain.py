#!/usr/bin/env python
"""
Brain — reads state/issues.json, decides what to do, logs the decision.

This is run by M3 (or any LLM agent) when it needs to process the active issue queue.
It produces a structured decision record that can be executed (low-risk) or escalated
(high-risk) to Duckets.

Usage:
    python brain.py                    # process all active issues
    python brain.py --dry-run          # show what it would decide
    python brain.py --issue <type>     # focus on one issue type

Decision categories:
    AUTO_FIX     — Brain executes the fix (restart container, kill process, etc.)
    ESCALATE     — Send to Duckets via Telegram with proposed action
    VERIFY       — Call Auditor (ChatGPT) for second opinion before deciding
    NOOP         — No action needed (false positive, known issue, etc.)
"""
import json
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

AGENT_HOME = Path.home() / "AgentShared"
STATE = AGENT_HOME / "state"
DECISIONS = AGENT_HOME / "decisions"
DECISIONS.mkdir(parents=True, exist_ok=True)


# Decision rules — what the Brain can do automatically vs escalate
# Each rule: (issue_type) -> (action, rationale, auto_execute?)
DECISION_RULES = {
    "miner_down": {
        "action": "AUTO_FIX",
        "fix": "Restart alpha-miner container via desktop launcher",
        "rationale": "Miner exits are common; auto-restart is safe and fast",
        "auto_execute": True,
    },
    "docker_down": {
        "action": "ESCALATE",
        "rationale": "Docker daemon down affects all containers — needs human judgment",
        "auto_execute": False,
    },
    "disk_full": {
        "action": "VERIFY",
        "rationale": "Disk cleanup can delete data; verify with Auditor before action",
        "auto_execute": False,
    },
    "gpu_idle": {
        "action": "ESCALATE",
        "rationale": "GPU idle could be many things (mode switch, miner stalled, etc.) — needs context",
        "auto_execute": False,
    },
    "mem_high": {
        "action": "NOOP",
        "rationale": "Memory pressure is normal during heavy work; only act if sustained >95%",
        "auto_execute": False,
    },
    "browseros_down": {
        "action": "ESCALATE",
        "rationale": "BrowserOS MCP affects many skills; needs judgment on whether to restart",
        "auto_execute": False,
    },
    "workers_offline": {
        "action": "ESCALATE",
        "rationale": "Remote workers offline could be network, power, or config — needs investigation",
        "auto_execute": False,
    },
    "log_error": {
        "action": "NOOP",
        "rationale": "Log errors are noisy; only act on patterns, not single occurrences",
        "auto_execute": False,
    },
    "lm_studio_loaded": {
        "action": "AUTO_FIX",
        "fix": "Unload LM Studio models to free VRAM for mining",
        "rationale": "Loaded models waste VRAM during mining hours",
        "auto_execute": True,
    },
}


def load_issues():
    issues_file = STATE / "issues.json"
    if not issues_file.exists():
        return {"active": [], "last_run": None}
    try:
        with open(issues_file) as f:
            return json.load(f)
    except:
        return {"active": [], "last_run": None}


def decide_on_issue(issue):
    """Apply decision rules to a single issue."""
    issue_type = issue.get("type", "unknown")
    rule = DECISION_RULES.get(issue_type, {
        "action": "ESCALATE",
        "rationale": f"Unknown issue type '{issue_type}' — needs human review",
        "auto_execute": False,
    })
    return {
        "issue": issue,
        "decision": rule["action"],
        "fix": rule.get("fix"),
        "rationale": rule["rationale"],
        "auto_execute": rule.get("auto_execute", False),
        "decided_at": datetime.now().isoformat(),
        "decided_by": os.environ.get("BOT_SQUAD_AGENT_NAME", "hermes"),  # who made this call
    }


def log_decision(decision):
    """Append decision to decisions/ log."""
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    issue_type = decision["issue"].get("type", "unknown")
    fname = DECISIONS / f"{ts}_{issue_type}.json"
    with open(fname, "w") as f:
        json.dump(decision, f, indent=2)
    return fname


def format_decision(decision):
    """Format for human/agent display."""
    issue = decision["issue"]
    return (
        f"  Type: {issue.get('type')} (level: {issue.get('level')})\n"
        f"  Msg:  {issue.get('msg')}\n"
        f"  -> Action: {decision['decision']}\n"
        f"     Rationale: {decision['rationale']}\n"
        f"     Auto-execute: {decision['auto_execute']}\n"
        f"     Fix: {decision.get('fix', 'N/A')}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show decisions without logging")
    parser.add_argument("--issue", type=str, help="Filter to one issue type")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    state = load_issues()
    issues = state.get("active", [])

    if args.issue:
        issues = [i for i in issues if i.get("type") == args.issue]

    if not issues:
        if args.json:
            print(json.dumps({"decisions": [], "summary": "no issues"}))
        else:
            print(f"No active issues (last watcher run: {state.get('last_run')})")
        return 0

    decisions = [decide_on_issue(i) for i in issues]

    if not args.dry_run:
        for d in decisions:
            log_decision(d)

    # Summarize
    auto = [d for d in decisions if d["decision"] == "AUTO_FIX"]
    escalate = [d for d in decisions if d["decision"] == "ESCALATE"]
    verify = [d for d in decisions if d["decision"] == "VERIFY"]
    noop = [d for d in decisions if d["decision"] == "NOOP"]

    summary = {
        "total": len(decisions),
        "auto_fix": len(auto),
        "escalate": len(escalate),
        "verify": len(verify),
        "noop": len(noop),
        "decisions": decisions,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"[BRAIN] processed {len(decisions)} issue(s):")
        print(f"   AUTO_FIX: {len(auto)}  ESCALATE: {len(escalate)}  VERIFY: {len(verify)}  NOOP: {len(noop)}\n")
        for d in decisions:
            print(format_decision(d))
            print()
        if not args.dry_run:
            print(f"[LOG] decisions written to {DECISIONS}/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
