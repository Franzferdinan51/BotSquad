# Bot Squad 🤖

**Three-agent autonomous system monitor for self-hosted AI infrastructure.**

Watcher (monitoring) + Brain (decisions) + Executor (actions). Runs on Windows, macOS, or Linux. Default engine: **Grok 4.3** for cost — easily swap to OpenClaw, Hermes, LM Studio, or any OpenAI-compatible endpoint via `config.yaml`.

## Why

Self-hosted AI setups have lots of moving parts — Docker containers, GPU workers, local model servers, browser automation, mining rigs, etc. When something breaks at 3am, you want it fixed before you wake up. Bot Squad does that:

1. **Watch** — poll system state every 2h (Docker, GPU, disk, memory, network, custom services)
2. **Decide** — apply rules to classify issues (AUTO_FIX / ESCALATE / VERIFY / NOOP)
3. **Act** — execute safe fixes automatically (restart containers, unload models, etc.)
4. **Alert** — Telegram the human for anything that needs judgment

## Quick start

```bash
git clone https://github.com/Franzferdinan51/BotSquad.git ~/AgentShared
cd ~/AgentShared
pip install pyyaml psutil  # or uv pip install ...
# Edit config.yaml — set your wallet/chat_id/thresholds
python scripts/orchestrator.py  # first run
```

Schedule it (every 2h):

**Windows (Task Scheduler):**
```powershell
powershell -ExecutionPolicy Bypass -File scripts/register-task.ps1
```

**macOS/Linux (cron):**
```bash
crontab -e
# Add: 0 */2 * * * cd ~/AgentShared && python3 scripts/orchestrator.py
```

## Architecture

```
  ┌──────────────────────┐
  │  Cron / Scheduler    │
  └──────────┬───────────┘
             ▼
  ┌──────────────────────┐
  │  orchestrator.py     │
  └──────────┬───────────┘
             │
     ┌───────┼───────┐
     ▼       ▼       ▼
  WATCHER  BRAIN  EXECUTOR
     │       │       │
     └───────┴───────┘
             ▼
     ~/AgentShared/    <- shared brain
       (state + decisions + plans + skills)
```

## Files

```
AgentShared/
├── README.md                          <- this file
├── config.yaml                        <- engine + thresholds
├── LICENSE                            <- MIT
├── CONTRIBUTING.md                    <- dev guide
├── SWAP_ENGINES.md                    <- engine swap guide
├── FUTURE_PLANS.md                    <- when to deploy agent-mesh-api
├── state/                             <- runtime state (gitignored)
├── decisions/                         <- audit trail (gitignored)
├── plans/                             <- long-form plans
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

## Engine swap

Change one line in `config.yaml`:

```yaml
engine: "openclaw"   # was "grok"
```

Built-in: `grok`, `openclaw`, `hermes`, `lmstudio`, `minimax`, `none`. Adding new engines is ~20 lines of Python — see `SWAP_ENGINES.md`.

## Customization

**Add a new auto-fix handler** → `scripts/executor.py`, edit `ACTION_REGISTRY`
**Add a new decision rule** → `scripts/brain.py`, edit `DECISION_RULES`
**Add a new check to Watcher** → `scripts/watcher.py`, add `check_X()` + wire into `collect_state()` + `find_issues()`

## Tested

- ✅ Detected real alpha-miner container exit (CRITICAL)
- ✅ Auto-restarted container via Executor
- ✅ GPU back to 100% in 5 seconds
- ✅ Telegram alerts with optional LLM enrichment
- ✅ All 3 pipeline steps run cleanly
- ✅ Engine swap works (Grok → OpenClaw = one config line)

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
- Built with assistance from Hermes (M3) on 2026-06-03
