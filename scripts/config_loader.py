#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
config_loader.py — single source of truth for Bot Squad config.

Reads ~/AgentShared/config.yaml. Falls back to defaults if missing.
All other scripts should `from config_loader import config` and use `config['key']`.

Also handles the engine abstraction — same interface for Grok, OpenClaw, Hermes, etc.
"""
import os
import json
import yaml
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

CONFIG_PATH = Path.home() / "AgentShared" / "config.yaml"

DEFAULTS = {
    "engine": "grok",
    "grok": {
        "api_base": "https://api.x.ai/v1",
        "api_key_env": "XAI_API_KEY",
        "model": "grok-4-3-fast",
        "timeout_seconds": 10,
    },
    "openclaw": {
        "base_url": "http://127.0.0.1:18789",
        "model": "default",
        "timeout_seconds": 15,
    },
    "hermes": {
        "base_url": "http://127.0.0.1:18793",
        "model": "default",
        "timeout_seconds": 15,
    },
    "lmstudio": {
        "base_url": "http://127.0.0.1:1234",
        "api_key_path": "~/.lmstudio/credentials/lmstudio-hub.json",
        "model": "default",
        "timeout_seconds": 30,
    },
    "minimax": {
        "api_base": "https://api.minimaxi.com/v1",
        "api_key_env": "MINIMAX_API_KEY",
        "model": "MiniMax-Text-01",
        "timeout_seconds": 30,
    },
    "telegram": {
        "enabled": True,
        "bot_token_env": "TELEGRAM_BOT_TOKEN",
        "chat_id": "588090613",
    },
    "thresholds": {
        "disk_warn_pct": 90,
        "disk_crit_pct": 95,
        "gpu_warn_pct": 50,
        "mem_warn_pct": 90,
        "expected_prl_workers": ["default", "mainpc", "vetgirl", "grievous"],
    },
    "schedule": {
        "interval_hours": 2,
        "auto_fix_cooldown_minutes": 5,
    },
    "prl": {
        "wallet": "prl1p5xxsuhhm4fvv72pvaz9hn4d8je6eahuxtet0nrlhxtjkfedpmews5pnwav",
        "pool_api": "https://pearl.alphapool.tech/api/miner",
    },
}


def load_config():
    """Load config from yaml, merging with defaults."""
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                user_cfg = yaml.safe_load(f) or {}
            _deep_merge(cfg, user_cfg)
        except Exception as e:
            print(f"[WARN] config.yaml load failed: {e}, using defaults")
    return cfg


def _deep_merge(base, override):
    """Recursively merge override into base."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


# Singleton
config = load_config()


def get_engine_config():
    """Return the config block for the active engine."""
    return config.get(config.get("engine", "grok"), {})


def call_llm(prompt, system=None, max_tokens=300):
    """
    Call the active engine with a prompt. Returns the response text.
    Same interface regardless of engine — this is the swappable layer.

    Used by Watcher to enrich plain alerts (e.g., "GPU is at 5%" → "GPU idle likely
    because miner container exited; recommend restart").

    If engine is 'none' or call fails, returns None.
    """
    engine = config.get("engine", "none")
    if engine == "none":
        return None

    try:
        if engine == "grok":
            return _call_grok(prompt, system, max_tokens)
        elif engine == "openclaw":
            return _call_openclaw(prompt, system, max_tokens)
        elif engine == "hermes":
            return _call_hermes(prompt, system, max_tokens)
        elif engine == "lmstudio":
            return _call_lmstudio(prompt, system, max_tokens)
        elif engine == "minimax":
            return _call_minimax(prompt, system, max_tokens)
        else:
            return None
    except Exception as e:
        print(f"[engine-error] {engine}: {e}")
        return None


def _call_grok(prompt, system, max_tokens):
    cfg = config["grok"]
    api_key = os.environ.get(cfg["api_key_env"], "")
    if not api_key:
        return None
    body = {
        "model": cfg["model"],
        "messages": [],
        "max_tokens": max_tokens,
    }
    if system:
        body["messages"].append({"role": "system", "content": system})
    body["messages"].append({"role": "user", "content": prompt})
    req = Request(
        f"{cfg['api_base']}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urlopen(req, timeout=cfg["timeout_seconds"]) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]


def _call_openclaw(prompt, system, max_tokens):
    """OpenClaw gateway — uses /v1/chat/completions style endpoint."""
    cfg = config["openclaw"]
    body = {
        "model": cfg["model"],
        "messages": [],
        "max_tokens": max_tokens,
    }
    if system:
        body["messages"].append({"role": "system", "content": system})
    body["messages"].append({"role": "user", "content": prompt})
    req = Request(
        f"{cfg['base_url']}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=cfg["timeout_seconds"]) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]


def _call_hermes(prompt, system, max_tokens):
    """Hermes agent gateway — same OpenAI-compatible endpoint."""
    cfg = config["hermes"]
    body = {
        "model": cfg["model"],
        "messages": [],
        "max_tokens": max_tokens,
    }
    if system:
        body["messages"].append({"role": "system", "content": system})
    body["messages"].append({"role": "user", "content": prompt})
    req = Request(
        f"{cfg['base_url']}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=cfg["timeout_seconds"]) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]


def _call_lmstudio(prompt, system, max_tokens):
    cfg = config["lmstudio"]
    token = ""
    cred_path = Path(os.path.expanduser(cfg["api_key_path"]))
    if cred_path.exists():
        try:
            with open(cred_path) as f:
                creds = json.load(f)
            key = creds.get("key", "")
            if isinstance(key, dict):
                token = key.get("keyId", "")
            else:
                token = key
        except:
            pass
    body = {
        "model": cfg["model"],
        "messages": [],
        "max_tokens": max_tokens,
    }
    if system:
        body["messages"].append({"role": "system", "content": system})
    body["messages"].append({"role": "user", "content": prompt})
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(
        f"{cfg['base_url']}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers=headers,
    )
    with urlopen(req, timeout=cfg["timeout_seconds"]) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]


def _call_minimax(prompt, system, max_tokens):
    cfg = config["minimax"]
    api_key = os.environ.get(cfg["api_key_env"], "")
    if not api_key:
        return None
    body = {
        "model": cfg["model"],
        "messages": [],
        "max_tokens": max_tokens,
    }
    if system:
        body["messages"].append({"role": "system", "content": system})
    body["messages"].append({"role": "user", "content": prompt})
    req = Request(
        f"{cfg['api_base']}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urlopen(req, timeout=cfg["timeout_seconds"]) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]


if __name__ == "__main__":
    # Test the loader
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    cfg = load_config()
    print(f"Engine: {cfg['engine']}")
    print(f"Thresholds: {cfg['thresholds']}")
    print(f"PRL workers expected: {cfg['thresholds']['expected_prl_workers']}")
    print(f"Schedule: every {cfg['schedule']['interval_hours']}h")
