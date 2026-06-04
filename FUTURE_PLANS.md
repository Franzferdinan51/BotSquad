# Future Plans - When to Deploy the Agent Mesh

The `agent-mesh-api` server (https://github.com/Franzferdinan51/agent-mesh-api) is **cloned but not running** on this box at `~/agent-mesh-api/`. It's a full agent-to-agent communication platform with task routing, presence tracking, semantic reactions, and a meta-agent orchestrator.

**Status:** ARCHIVED — not in use. Defer until 3+ agents exist.

## When to deploy

The mesh becomes worth the complexity when we have **3+ agents** that need to:
- **Discover each other** without hardcoded IDs (mesh handles name resolution)
- **Route tasks to the best-fit agent** based on capabilities (mesh-meta-agent does this)
- **Coordinate on shared work** with state machine (mesh tasks with pending→in_progress→completed)
- **Audit cross-agent activity** in one place (mesh activity feed)
- **React to each other's output** semantically (👍=ACK, 👎=REJECT, 🔥=URGENT)

## What triggers deployment

| Trigger | Deploy the mesh? |
|---|---|
| 2 agents (current: Hermes + OpenClaw) | ❌ No — file drops work fine |
| 3 agents (added subagent) | ⚠️ Maybe — depends on coordination needs |
| 4+ agents OR cross-VPS agents | ✅ Yes — definitely worth it |
| Agents need to negotiate tasks (not just receive them) | ✅ Yes |
| Cross-team visibility into what agents are doing | ✅ Yes |

## What "deploy" means when we get there

1. `cd ~/agent-mesh-api && node server.js` — start port 4000 (5 sec)
2. Drop `agent-mesh` skill into each agent's workspace:
   - `cp -r ~/agent-mesh-api/skills/agent-mesh ~/.openclaw/workspace/skills/`
3. Each agent registers with `mesh_register` on startup
4. Migrate Bot Squad to use `mesh_send_message` for issues + `mesh_get_messages` for brain reads
5. Optionally start `node mesh-meta-agent.js` (port 4001) for auto-routing

**Estimated migration time:** 30-60 min. The mesh's `SKILL_PROTOCOL.md` documents the exact integration pattern.

## Why not now

- 2 agents talking via `~/AgentShared/` JSON files: works perfectly
- Migration overhead: ~30 min of coding + testing + debugging the integration
- Current pain: zero. Bot Squad proved end-to-end (caught real alpha-miner crash, auto-restarted, audit trail intact)
- Mesh's value at 2 agents: almost none. We don't need task routing when there's only 1 task source.

## What to revisit

When the next agent gets added (or you start wanting "agents to talk to each other" in a more structured way), come back to this doc.

**Reference:** https://github.com/Franzferdinan51/agent-mesh-api
**Local clone:** `~/agent-mesh-api/`
**Documentation:** README.md, API_DOCUMENTATION.md, SKILL.md, SKILL_PROTOCOL.md (all in the repo)

## Selective use without full migration

**If only ONE specific feature is needed**, Hermes can start the mesh server (`node server.js` on port 4000) and use just that endpoint — without migrating all of Bot Squad. Examples:

- **Just need task state tracking?** Start server, use `POST /api/tasks` only
- **Just need cross-agent presence?** Use `GET /api/capabilities`
- **Just need a shared blackboard for a specific workflow?** Use `POST /api/memory` (group collective memory)

**Rule of thumb:** Start mesh server on demand, use the specific endpoint needed, leave the rest of Bot Squad on file-based coordination. Don't migrate wholesale unless full coordination is needed.

When in doubt, ask Duckets before starting the server (it's a 5-min deploy but adds a running process).
