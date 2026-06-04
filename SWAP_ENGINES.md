# Swapping Engines - Quick Guide

The Bot Squad uses an **engine abstraction layer** in `config_loader.py`. To change which AI powers the Watcher (and any future LLM calls), you change ONE line in `config.yaml`.

## Current default: Grok 4.3

```yaml
engine: "grok"
```

**Pros:** Cheap (~$0.005/run), fast, good at structured output
**Cons:** External (xAI API), needs `XAI_API_KEY` env var

## How to swap to OpenClaw (Duckets already has this set up)

### 1. Edit `config.yaml`

```yaml
engine: "openclaw"   # was "grok"
```

That's the only required change.

### 2. (Optional) Disable manual Telegram in Watcher

OpenClaw has its own Telegram routing, so you can stop the Watcher from sending manually:

```yaml
telegram:
  enabled: false   # was true
```

Then add the OpenClaw agent as a subscriber to Watcher alerts — or just let OpenClaw poll the state files.

### 3. (Optional) Tell Watcher to use OpenClaw's model

```yaml
openclaw:
  base_url: "http://127.0.0.1:18789"   # OpenClaw gateway
  model: "default"                     # or specify a model
  timeout_seconds: 15
```

### 4. Test

```bash
cd C:\Users\franz\AgentShared
python scripts\watcher.py
```

You should see:
```
[2026-...-03T...] === Watcher run started ===
[2026-...-03T...] Engine: openclaw
```

If OpenClaw is running and responsive, the LLM enrichment calls will go through it.

### 5. If you want to commit

```powershell
Start-ScheduledTask -TaskName 'BotSquadOrchestrator'   # run once to verify
```

Or wait for the next 2h cycle.

## How to swap to other engines

Same pattern. Edit `config.yaml`:

```yaml
engine: "hermes"      # local Hermes gateway on 18793
engine: "lmstudio"    # local LM Studio on 1234
engine: "minimax"     # MiniMax M3 direct API
engine: "none"        # disable LLM calls, rules only
```

Each engine has its own config block. Default URLs/keys are pre-filled.

## How the swap works under the hood

`config_loader.py` has one function: `call_llm(prompt, system, max_tokens)`. It dispatches to the right endpoint based on `config["engine"]`. Every script that needs an LLM calls this function — so they all swap together.

To add a NEW engine (e.g., Ollama, LM Studio remote, etc.):
1. Add a config block in `config.yaml`:
   ```yaml
   my_new_engine:
     base_url: "http://..."
     api_key_env: "MY_API_KEY"
     model: "..."
     timeout_seconds: 30
   ```
2. Add a `_call_my_new_engine(prompt, system, max_tokens)` function in `config_loader.py`
3. Add an `elif` in `call_llm()`

That's it. ~20 lines of Python.

## When to swap?

- **Grok 4.3** (default) — when you want cheap, fast, and don't mind external
- **OpenClaw** — when you want everything in your own gateway, with built-in messaging
- **Hermes** — when running on the same box and want zero external deps
- **LM Studio** — when you want full local control
- **MiniMax M3** — when you want the best reasoning, can pay for it
- **none** — when you only want rule-based alerts, no LLM cost

The system works in `none` mode (rules only) — you'll just lose the "Insight:" line in alerts.
