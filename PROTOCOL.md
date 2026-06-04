# Bot Squad Protocol — Hermes ↔ OpenClaw Coordination Contract

**This is the missing piece.** Both agents (Hermes, OpenClaw) implement the same protocol. They don't need to know about each other — they just need to know how to read and write the shared brain at `~/AgentShared/`.

## The contract

### Read side (both agents do this)

```python
from pathlib import Path

SHARED = Path.home() / "AgentShared"

# Active issues — the queue
issues = json.loads((SHARED / "state" / "issues.json").read_text())

# Recent decisions — what was decided
decisions = sorted((SHARED / "decisions").glob("*.json"))

# Plans — multi-step work in progress
plans = list((SHARED / "plans").glob("*.md"))
```

### Write side (each agent has its own role)

**Watcher (cron, scheduled):**
- Writes `state/current.json` (overwrites — it's a snapshot)
- Writes `state/issues.json` (overwrites with dedup vs last run)
- Does NOT write decisions
- Does NOT write plans

**Brain (Hermes, when triggered):**
- Reads `state/issues.json`
- Writes `decisions/<timestamp>_<type>.json` — one per issue
- Optionally writes `plans/<topic>.md` for multi-step work
- Does NOT modify state/

**Executor (cron or manual):**
- Reads `decisions/*.json` where `decision == "AUTO_FIX"`
- Updates the decision file with `executed: true` + result
- Does NOT modify state/

### Reaction rules

1. **Watcher never acts** — it only reports
2. **Brain never executes** — it only decides
3. **Executor never decides** — it only acts on existing decisions
4. **Both agents can read everything** — no read restrictions
5. **Writes are role-specific** — see above

## File ownership

| Path | Watcher | Brain | Executor | Both read |
|---|---|---|---|---|
| `state/current.json` | writes | — | — | yes |
| `state/issues.json` | writes | — | — | yes |
| `decisions/*.json` | — | writes | updates | yes |
| `plans/*.md` | — | writes | — | yes |
| `skills/*.md` | — | writes | — | yes |
| `logs/*.log` | writes | writes | writes | yes |

## How to onboard OpenClaw

OpenClaw needs three things to participate:

1. **Know about the shared brain.** Tell it `~/AgentShared/` exists and what's in it.
2. **Read state on a schedule.** Have it poll `state/issues.json` periodically (or use the Watcher's cron output).
3. **Write decisions when it makes them.** When OpenClaw decides something, write to `decisions/` per the schema below.

The simplest integration:

```bash
# In OpenClaw's HEARTBEAT or a periodic check:
cat ~/AgentShared/state/issues.json | jq '.active[]'

# When OpenClaw decides:
echo '{"issue":..., "decision":"ESCALATE", "rationale":"..."}' \
  > ~/AgentShared/decisions/$(date -Iseconds)_my_issue.json
```

OpenClaw's existing toolset (filesystem, shell, JSON) is enough — no custom integration needed.

## Decision schema

```json
{
  "issue": {
    "level": "CRITICAL | WARN | INFO",
    "type": "string (snake_case)",
    "msg": "human-readable description"
  },
  "decision": "AUTO_FIX | ESCALATE | VERIFY | NOOP",
  "fix": "string (what to do, if applicable)",
  "rationale": "string (why this decision)",
  "auto_execute": true,
  "decided_at": "ISO 8601 timestamp",
  "decided_by": "string (which agent — 'hermes', 'openclaw', 'manual')",
  "executed": false,
  "executed_at": null,
  "execution_result": null
}
```

The `decided_by` field is what tells you which agent made the call. Add it when you write a decision so the audit trail is clear.

## Plan schema

Plans are freeform markdown, but the recommended structure:

```markdown
# <Plan Title>

**Created:** <ISO timestamp>
**Owner:** hermes | openclaw | shared
**Status:** draft | in_progress | completed | cancelled

## Goal
<what this plan achieves>

## Steps
1. <step 1>
2. <step 2>
3. ...

## Notes
<freeform — discoveries, blockers, learnings>
```

## Why file-based (not HTTP / not mesh)?

- **No network deps** — works offline, no port conflicts
- **Trivial to debug** — `cat state/issues.json` shows you everything
- **No race conditions** in practice (write-once, read-many pattern)
- **Git-trackable** — decisions and plans can be versioned
- **Both agents already have filesystem tools** — no new integration needed

When to upgrade to `agent-mesh-api` (HTTP, port 4000): see `FUTURE_PLANS.md`. TL;DR: not until you have 3+ agents or need cross-VPS coordination.
