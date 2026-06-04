# Contributing to Bot Squad

## Dev workflow

```bash
# 1. Make changes in ~/AgentShared/ (this IS the repo)
# 2. Test locally
python scripts/orchestrator.py
# 3. Commit
git add -A
git commit -m "type(scope): description"
# 4. Push
git push origin main
```

## Commit message format

```
type(scope): short description

[optional body]

[optional footer]
```

**Types:** `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `style`
**Scope (optional):** `watcher`, `brain`, `executor`, `config`, `docs`

**Examples:**
- `feat(watcher): add PRL pool auto-failover check`
- `fix(executor): handle missing launcher gracefully`
- `docs: update SWAP_ENGINES with LM Studio notes`

## Architecture rules

1. **All scripts read from `config.yaml`** — no hardcoded values that should be configurable
2. **All LLM calls go through `config_loader.call_llm()`** — never hit an API directly
3. **No secrets in code** — env vars only
4. **State files in `state/` are gitignored** — never commit runtime data
5. **Decisions go in `decisions/`** — gitignored, but the schema is documented below

## Decision schema

When Brain processes an issue, it writes a JSON file to `decisions/`:

```json
{
  "issue": {
    "level": "CRITICAL",
    "type": "miner_down",
    "msg": "alpha-miner container exited"
  },
  "decision": "AUTO_FIX",
  "fix": "Restart alpha-miner container via desktop launcher",
  "rationale": "Miner exits are common; auto-restart is safe and fast",
  "auto_execute": true,
  "decided_at": "2026-06-03T22:02:41.123456",
  "executed": true,
  "executed_at": "2026-06-03T22:02:42.000000",
  "execution_result": {
    "success": true,
    "message": "launcher rc=0"
  }
}
```

## Testing before commit

```bash
# 1. Lint
python -c "import ast; ast.parse(open('scripts/watcher.py').read())"  # all scripts
python -c "import ast; ast.parse(open('scripts/brain.py').read())"
python -c "import ast; ast.parse(open('scripts/executor.py').read())"
python -c "import ast; ast.parse(open('scripts/orchestrator.py').read())"
python -c "import ast; ast.parse(open('scripts/config_loader.py').read())"

# 2. Run full pipeline
python scripts/orchestrator.py

# 3. Verify state file
cat state/current.json | python -m json.tool

# 4. Verify decisions were logged
ls decisions/
```

## Versioning

Semver: `MAJOR.MINOR.PATCH`
- **MAJOR** — breaking config schema changes (engine swap API changes)
- **MINOR** — new features (new check, new auto-fix, new engine)
- **PATCH** — bug fixes, doc updates

Tag releases: `git tag -a v1.0.0 -m "Initial release"` then `git push --tags`.

## Pull request flow

(For solo dev, this is more documentation than process. When collaborators join:)
1. Branch: `git checkout -b feat/your-feature`
2. Commit on the branch
3. Test
4. Push: `git push origin feat/your-feature`
5. Open PR on GitHub
6. Self-review, merge

## Adding a new engine

See `SWAP_ENGINES.md` for the 20-line pattern. In short:
1. Add a config block in `config.yaml`
2. Add `_call_my_engine(prompt, system, max_tokens)` in `config_loader.py`
3. Add an `elif` branch in `call_llm()`

## Adding a new check to Watcher

```python
def check_my_thing():
    """Docstring."""
    # ... return dict with results

# In collect_state():
def collect_state():
    return {
        # ...
        "my_thing": check_my_thing(),
    }

# In find_issues():
def find_issues(state):
    issues = []
    # ...
    if state["my_thing"].get("problematic"):
        issues.append({"level": "WARN", "type": "my_thing", "msg": "..."})
    return issues
```

## Adding a new decision rule

```python
# In brain.py:
DECISION_RULES = {
    "my_new_issue": {
        "action": "AUTO_FIX",  # or ESCALATE / VERIFY / NOOP
        "fix": "What the executor should do",
        "rationale": "Why this is safe to auto-execute",
        "auto_execute": True,
    },
}
```

## Adding a new auto-fix handler

```python
# In executor.py:
def my_new_fix():
    """Implementation."""
    # ... return (success: bool, message: str)

ACTION_REGISTRY = {
    "my_new_issue": (my_new_fix, ()),
    # ...
}
```
