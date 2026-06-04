# Bot Squad 🤖

**Coordination layer for Hermes (M3) and OpenClaw to work together as a team.**

A shared brain (file-based, no DB), a scheduled watcher, and a decision engine. Hermes and OpenClaw both read from and write to the same `~/AgentShared/` directory — Bot Squad is the protocol that lets them hand off tasks, share context, and act on each other's findings.

## Why

Hermes and OpenClaw are both general-purpose agents. On their own, they're isolated — each one has its own context, its own memory, its own decisions. **Bot Squad is the thing that makes them a team.**

- **Watcher** runs on a schedule, polls system state, posts findings
- **Brain** (Hermes, you, when triggered) reads findings, decides what to do
- **Executor** carries out safe fixes
- **Telegram** keeps you (Duckets) in the loop for anything needing judgment

Hermes and OpenClaw both implement the same `bot-squad-protocol` — they read state, write decisions, react to each other's outputs. They don't have to know about each other; they just have to know about the shared brain.

## Architecture

```
        ┌─────────────────┐
        │  Cron (2h)      │
        └────────┬────────┘
                 ▼
        ┌─────────────────┐
        │  orchestrator   │
        └────────┬────────┘
                 │
       ┌─────────┼─────────┐
       ▼         ▼         ▼
    WATCHER   BRAIN     EXECUTOR
       │         │         │
       └─────────┴─────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ ~/AgentShared/  │   <-- shared brain
        │  state/         │       (Hermes + OpenClaw both read/write)
        │  decisions/     │
        │  plans/         │
        │  skills/        │
        └─────────────────┘
                 ▲
                 │
       ┌─────────┴─────────┐
       │                   │
   ┌───┴────┐         ┌────┴───┐
   │ Hermes │         │OpenClaw│
   │  (M3)  │         │        │
   └────────┘         └────────┘
```

Both agents see the same `state/`, `decisions/`, and `plans/` files. They react to each other through the filesystem. No network calls between them needed for coordination.

## Quick start

```bash
git clone https://github.com/Franzferdinan51/BotSquad.git ~/AgentShared
cd ~/AgentShared
uv pip install pyyaml psutil --system  # or pip install
# Edit config.yaml — set your wallet, Telegram chat_id, thresholds
python scripts/orchestrator.py  # test it
```

**Schedule (every 2h):**
- Windows: `powershell -ExecutionPolicy Bypass -File scripts/register-task.ps1`
- macOS/Linux: add to crontab: `0 */2 * * * cd ~/AgentShared && python3 scripts/orchestrator.py`

## The protocol

**Watcher writes:**
- `state/current.json` — full system snapshot
- `state/issues.json` — active problems (deduped)

**Brain writes:**
- `decisions/YYYY-MM-DDTHH-MM-SS_<type>.json` — one file per decision
- `plans/*.md` — long-form plans when needed

**Executor reads:**
- `decisions/*.json` where `decision == "AUTO_FIX"`
- Runs the fix, updates the decision file with result

**Both Hermes and OpenClaw:**
- Read `state/issues.json` to see what's broken
- Read `decisions/` to see what was decided
- Write to `plans/` when they need to share a multi-step plan
- Write to `skills/` when they learn something reusable

**Reaction contract (recommended):**
- Watcher finds issue → writes to `state/issues.json` with type + level
- Brain reads → writes decision → either auto-executes (Executor) or alerts Duckets
- Both agents can read each other's decisions to build context

## Engine config

The LLM engine is configurable via `config.yaml`:

```yaml
engine: "grok"   # or openclaw / hermes / lmstudio / minimax / none
```

This is what powers the Watcher's LLM enrichment ("Insight: GPU is idle because miner container exited"). **Note:** This is NOT the Hermes-vs-OpenClaw switch — those are the agents. The engine is just which LLM the Watcher asks for triage context.

**To swap:**
```bash
# Edit config.yaml: change `engine: "grok"` to your preferred model
# No code change needed. Restart the scheduled task.
```

See `SWAP_ENGINES.md` for the full list (grok, openclaw, hermes, lmstudio, minimax, none).

## Files

```
AgentShared/
├── README.md                          <- this file
├── config.yaml                        <- engine + thresholds
├── LICENSE                            <- MIT
├── CONTRIBUTING.md                    <- dev guide + protocol details
├── SWAP_ENGINES.md                    <- engine swap guide
├── FUTURE_PLANS.md                    <- when to upgrade to agent-mesh-api
├── state/                             <- runtime state (gitignored)
├── decisions/                         <- audit trail (gitignored)
├── plans/                             <- shared plans (Hermes + OpenClaw both write)
├── skills/                            <- learned skills (gitignored)
├── logs/                              <- activity logs (gitignored)
└── scripts/
    ├── config_loader.py               <- engine abstraction
    ├── watcher.py                     <- state collector + LLM enrichment
    ├── brain.py                       <- decision rules
    ├── executor.py                    <- action taker
    ├── orchestrator.py                <- pipeline runner
    ├── run-orchestrator.cmd           <- Windows wrapper
    └── register-task.ps1              <- Windows scheduler setup
```

## Customization

**Add a new check to Watcher:**
Edit `scripts/watcher.py`, add `check_X()` + wire into `collect_state()` + `find_issues()`.

**Add a new decision rule:**
Edit `scripts/brain.py`, add to `DECISION_RULES`.

**Add a new auto-fix:**
Edit `scripts/executor.py`, add to `ACTION_REGISTRY`.

**Make OpenClaw participate:**
Have OpenClaw read `~/AgentShared/state/issues.json` on a schedule and write decisions to `~/AgentShared/decisions/`. The protocol is just "read state, write decisions" — OpenClaw's existing toolset can do this.

**Make Hermes participate:**
Already wired — Hermes (me) reads `decisions/` when you ask, and writes plans to `plans/` when working on multi-step tasks.

## Proven

- ✅ Detected real alpha-miner container exit (CRITICAL)
- ✅ Auto-restarted via Executor in 5 seconds
- ✅ GPU back to 100% hashing
- ✅ Telegram alerts with optional LLM enrichment
- ✅ All 3 pipeline steps run cleanly

## Cost

| Cycle | Cost |
|---|---|
| All-green | ~$0.005 (Grok 4.3) or $0 (engine=none) |
| One auto-fix | +$0 |
| Auditor called | +$0.05 (ChatGPT) |
| **Daily estimate** | **~$0.05-0.15** |

## License

MIT — see [LICENSE](LICENSE).

## Author

Ryan "Duckets" Franz Ferdinand
- [github.com/Franzferdinan51](https://github.com/Franzferdinan51)
- Built with Hermes (M3) on 2026-06-03
