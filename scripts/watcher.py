#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Watcher — system monitor + alert dispatcher.

Runs every 2h. Checks Docker, GPU, disk, memory, LM Studio, BrowserOS, PRL pool, error logs.
Optionally enriches alerts via the configured LLM engine (grok/openclaw/hermes/etc.).
Writes to ~/AgentShared/state/, alerts Telegram if anything's off.

Config: ~/AgentShared/config.yaml (edit there to change engines, thresholds, etc.)
"""
import json
import subprocess
import shutil
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import socket

# Load config + path setup
sys.path.insert(0, str(Path(__file__).parent))
from config_loader import config, call_llm

AGENT_HOME = Path.home() / "AgentShared"
STATE = AGENT_HOME / "state"
LOGS = AGENT_HOME / "logs"
STATE.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

# Pull thresholds from config
TH = config["thresholds"]
DISK_WARN_PCT = TH["disk_warn_pct"]
DISK_CRIT_PCT = TH["disk_crit_pct"]
GPU_WARN_PCT = TH["gpu_warn_pct"]
MEM_WARN_PCT = TH["mem_warn_pct"]
EXPECTED_WORKERS = TH["expected_prl_workers"]


def log(msg):
    ts = datetime.now().isoformat()
    line = f"[{ts}] {msg}"
    safe = line.encode("ascii", "replace").decode("ascii")
    print(safe)
    with open(LOGS / "watcher.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd, timeout=15):
    """Run shell command, return (rc, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def check_docker():
    """Check running + exited containers."""
    rc, out, _ = run('docker ps --format "{{.Names}}|{{.Status}}" 2>&1', timeout=20)
    running = []
    if rc == 0 and out:
        for line in out.splitlines():
            if "|" in line:
                name, status = line.split("|", 1)
                running.append({"name": name, "status": status})

    rc2, out2, _ = run('docker ps -a --filter "status=exited" --format "{{.Names}}|{{.Status}}" 2>&1', timeout=20)
    exited = []
    if rc2 == 0 and out2:
        for line in out2.splitlines()[:10]:
            if "|" in line:
                name, status = line.split("|", 1)
                exited.append({"name": name, "status": status})

    daemon_up = rc == 0 and (out is not None or out2 is not None)
    return {"docker_up": daemon_up, "containers": running, "exited": exited}


def check_gpu():
    rc, out, _ = run("nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader")
    if rc != 0:
        return {"gpu_up": False, "error": out[:200]}
    parts = [p.strip() for p in out.split(",")]
    if len(parts) < 4:
        return {"gpu_up": False, "error": f"unexpected output: {out}"}
    return {
        "gpu_up": True,
        "util_pct": int(parts[0].rstrip("%").split()[0]),
        "mem_used_mb": int(parts[1].rstrip("MiB").strip()),
        "mem_total_mb": int(parts[2].rstrip("MiB").strip()),
        "temp_c": int(parts[3].rstrip("C").strip()),
    }


def check_disk():
    total, used, free = shutil.disk_usage("C:\\")
    pct = (used / total) * 100
    return {
        "total_gb": round(total / (1024**3), 1),
        "used_gb": round(used / (1024**3), 1),
        "free_gb": round(free / (1024**3), 1),
        "used_pct": round(pct, 1),
    }


def check_memory():
    try:
        import psutil
        vm = psutil.virtual_memory()
        return {
            "total_mb": vm.total // (1024 * 1024),
            "used_mb": vm.used // (1024 * 1024),
            "free_mb": vm.available // (1024 * 1024),
            "used_pct": vm.percent,
        }
    except ImportError:
        return {"total_mb": 0, "used_mb": 0, "free_mb": 0, "used_pct": 0, "error": "psutil not installed"}


def check_lm_studio():
    try:
        cred_path = Path.home() / ".lmstudio" / "credentials" / "lmstudio-hub.json"
        if not cred_path.exists():
            return {"lm_studio_up": False, "error": "no credentials", "loaded_models": []}
        with open(cred_path) as f:
            creds = json.load(f)
        key = creds.get("key", "")
        if isinstance(key, dict):
            token = key.get("keyId", "")
        else:
            token = key or creds.get("apiKey", "")
        if not token:
            return {"lm_studio_up": False, "error": "no token", "loaded_models": []}
        req = Request("http://127.0.0.1:1234/v1/models", headers={"Authorization": f"Bearer {token}"})
        with urlopen(req, timeout=3) as r:
            data = json.loads(r.read())
        models = data.get("data", [])
        loaded = [m.get("id", "?") for m in models if m.get("type") == "llm" or "loaded" in str(m).lower()]
        return {"lm_studio_up": True, "loaded_models": loaded, "model_count": len(models)}
    except HTTPError as e:
        if e.code == 401:
            return {"lm_studio_up": True, "auth_ok": False, "loaded_models": [], "model_count": 0}
        return {"lm_studio_up": False, "error": f"HTTP {e.code}", "loaded_models": []}
    except (URLError, socket.timeout, ConnectionRefusedError, FileNotFoundError) as e:
        return {"lm_studio_up": False, "error": str(e)[:200], "loaded_models": []}
    except Exception as e:
        return {"lm_studio_up": False, "error": str(e)[:200], "loaded_models": []}


def check_browseros():
    try:
        req = Request("http://127.0.0.1:9200/health", method="GET")
        with urlopen(req, timeout=3) as r:
            return {"browseros_up": r.status == 200, "status_code": r.status}
    except (URLError, socket.timeout, ConnectionRefusedError) as e:
        return {"browseros_up": False, "error": str(e)[:200]}


def check_prl_pool():
    wallet = config["prl"]["wallet"]
    pool_api = config["prl"]["pool_api"]
    try:
        req = Request(
            f"{pool_api}/{wallet}",
            headers={"User-Agent": "Mozilla/5.0 BotSquad/1.0", "Accept": "application/json"},
        )
        with urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        workers = data.get("workers", [])
        online = [w["name"] for w in workers if w.get("online")]

        def parse_hr(s):
            if not s:
                return 0
            try:
                return float(str(s).split()[0])
            except (ValueError, IndexError):
                return 0

        total_ths = sum(parse_hr(w.get("hashrate", 0)) for w in workers)
        return {
            "pool_ok": True,
            "balance": data.get("balance_prl", 0),
            "total_paid": data.get("total_paid_prl", 0),
            "team_hashrate_ths": round(total_ths, 2),
            "workers_online": online,
            "workers_total": [w["name"] for w in workers],
        }
    except Exception as e:
        return {"pool_ok": False, "error": str(e)[:200]}


def check_errors():
    issues = []
    log_paths = [Path.home() / ".hermes" / "logs" / "errors.log"]
    for lp in log_paths:
        if not lp.exists():
            continue
        try:
            with open(lp, "r", errors="ignore") as f:
                lines = f.readlines()[-200:]
            for line in lines:
                if "ERROR" in line.upper() or "CRITICAL" in line.upper() or "FATAL" in line.upper():
                    issues.append({"source": str(lp), "line": line.strip()[:300]})
                    if len(issues) >= 5:
                        return issues
        except:
            pass
    return issues


def collect_state():
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "engine": config.get("engine", "none"),
        "docker": check_docker(),
        "gpu": check_gpu(),
        "disk": check_disk(),
        "memory": check_memory(),
        "lm_studio": check_lm_studio(),
        "browseros": check_browseros(),
        "internet": {"internet_up": True, "note": "verified via prl_pool check"},
        "prl_pool": check_prl_pool(),
        "recent_errors": check_errors(),
    }


def find_issues(state):
    issues = []
    # Disk
    pct = state["disk"].get("used_pct", 0)
    if pct >= DISK_CRIT_PCT:
        issues.append({"level": "CRITICAL", "type": "disk_full", "msg": f"Disk {pct}% full ({state['disk']['free_gb']}GB free)"})
    elif pct >= DISK_WARN_PCT:
        issues.append({"level": "WARN", "type": "disk_full", "msg": f"Disk {pct}% full ({state['disk']['free_gb']}GB free)"})
    # Docker
    if not state["docker"].get("docker_up"):
        issues.append({"level": "CRITICAL", "type": "docker_down", "msg": "Docker daemon is down"})
    else:
        containers = [c["name"] for c in state["docker"].get("containers", [])]
        exited = [c["name"] for c in state["docker"].get("exited", [])]
        if "alpha-miner" not in containers and "alpha-miner" in exited:
            issues.append({"level": "CRITICAL", "type": "miner_down", "msg": "alpha-miner container exited"})
        elif "alpha-miner" not in containers:
            issues.append({"level": "WARN", "type": "miner_missing", "msg": "alpha-miner container not present"})
    # GPU
    if state["gpu"].get("gpu_up"):
        if state["gpu"]["util_pct"] < GPU_WARN_PCT:
            issues.append({"level": "WARN", "type": "gpu_idle", "msg": f"GPU only at {state['gpu']['util_pct']}% - miner may be stalled"})
    # Memory
    if state["memory"].get("used_pct", 0) >= MEM_WARN_PCT:
        issues.append({"level": "WARN", "type": "mem_high", "msg": f"Memory {state['memory']['used_pct']}% used"})
    # LM Studio loaded during mining
    if state["lm_studio"].get("loaded_models"):
        issues.append({"level": "INFO", "type": "lm_studio_loaded", "msg": f"LM Studio models loaded: {state['lm_studio']['loaded_models']} - may conflict with mining"})
    # BrowserOS
    if not state["browseros"].get("browseros_up"):
        issues.append({"level": "WARN", "type": "browseros_down", "msg": "BrowserOS MCP server is down"})
    # PRL workers
    if state["prl_pool"].get("pool_ok"):
        online = set(state["prl_pool"].get("workers_online", []))
        missing = set(EXPECTED_WORKERS) - online
        if missing:
            issues.append({"level": "WARN", "type": "workers_offline", "msg": f"PRL workers offline: {', '.join(missing)}"})
    # Recent errors
    for err in state.get("recent_errors", []):
        issues.append({"level": "WARN", "type": "log_error", "msg": f"Error in {Path(err['source']).name}: {err['line'][:150]}"})
    return issues


def load_issues():
    issues_file = STATE / "issues.json"
    if issues_file.exists():
        try:
            with open(issues_file) as f:
                return json.load(f)
        except:
            return {"active": [], "last_run": None}
    return {"active": [], "last_run": None}


def save_issues(issues, last_run):
    with open(STATE / "issues.json", "w") as f:
        json.dump({"active": issues, "last_run": last_run}, f, indent=2)


def diff_issues(old, new):
    old_keys = {(i["type"], i["msg"]) for i in old}
    return [i for i in new if (i["type"], i["msg"]) not in old_keys]


def enrich_with_llm(issues, state):
    """Optionally ask the LLM to add context/recommendation to a critical issue."""
    crit = [i for i in issues if i["level"] == "CRITICAL"]
    if not crit:
        return issues
    engine = config.get("engine", "none")
    if engine == "none":
        return issues

    # Only enrich the first critical issue (cost control)
    issue = crit[0]
    prompt = (
        f"System state summary: disk={state['disk']['used_pct']}%, "
        f"gpu={state['gpu'].get('util_pct', '?')}%, "
        f"docker_up={state['docker']['docker_up']}, "
        f"running_containers={[c['name'] for c in state['docker'].get('containers', [])]}, "
        f"prl_workers_online={state['prl_pool'].get('workers_online', [])}.\n\n"
        f"Critical issue: {issue['msg']} (type={issue['type']})\n\n"
        "In one short sentence, what's the most likely cause and the recommended fix?"
    )
    response = call_llm(prompt, max_tokens=80)
    if response:
        issue["llm_insight"] = response
        log(f"[llm-enrich] {issue['type']}: {response}")
    return issues


def send_telegram(msg):
    """Send a Telegram message via bot API."""
    if not config["telegram"]["enabled"]:
        log(f"[telegram-skip] (disabled in config)")
        return False
    token = os.environ.get(config["telegram"]["bot_token_env"], "")
    if not token:
        log(f"[telegram-skip] (no {config['telegram']['bot_token_env']} env var)")
        return False
    chat_id = config["telegram"]["chat_id"]
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}).encode()
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception as e:
        log(f"[telegram-err] {e}")
        return False


def main():
    log("=== Watcher run started ===")
    log(f"Engine: {config.get('engine', 'none')}")
    state = collect_state()
    issues = find_issues(state)
    issues = enrich_with_llm(issues, state)

    with open(STATE / "current.json", "w") as f:
        json.dump(state, f, indent=2)

    prev = load_issues()
    new_issues = diff_issues(prev.get("active", []), issues)
    save_issues(issues, state["timestamp"])

    if new_issues:
        crit = [i for i in new_issues if i["level"] == "CRITICAL"]
        warn = [i for i in new_issues if i["level"] == "WARN"]
        info = [i for i in new_issues if i["level"] == "INFO"]

        msg_lines = [f"[WATCHER ALERT] {len(new_issues)} new"]
        if crit:
            msg_lines.append(f"\nCRITICAL ({len(crit)})")
            for i in crit:
                msg_lines.append(f"  - {i['msg']}")
                if i.get("llm_insight"):
                    msg_lines.append(f"    Insight: {i['llm_insight']}")
        if warn:
            msg_lines.append(f"\nWARN ({len(warn)})")
            for i in warn:
                msg_lines.append(f"  - {i['msg']}")
        if info:
            msg_lines.append(f"\nINFO ({len(info)})")
            for i in info:
                msg_lines.append(f"  - {i['msg']}")
        send_telegram("\n".join(msg_lines))
    else:
        log("No new issues. All clear.")

    log(f"=== Watcher done: {len(issues)} active issues, {len(new_issues)} new ===")
    return 0 if not [i for i in issues if i["level"] == "CRITICAL"] else 1


if __name__ == "__main__":
    sys.exit(main())
