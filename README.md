# Bot Squad — Paused

**Status: Stopped / archived for now.**

This project is on hold. See [Agent-Teams](https://github.com/Franzferdinan51/Agent-Teams) for the active multi-agent coordination layer.

## Why

BotSquad was a small Python watcher/brain/executor loop meant to share state between Hermes and OpenClaw. After building it, I found out the more complete Hive Nation stack already exists in Agent-Teams (Council server, Senate, mesh, LLM deliberation). Running both would be maintenance overhead for no gain.

## Resuming

If we ever come back to this, the parts worth keeping were:
- File-based shared brain (`~/AgentShared/`) — no server, no DB
- `decided_by` audit field on every decision
- Hermes / OpenClaw writing JSON to the same directory

But: just port those into Agent-Teams as a profile, don't maintain a second system.
