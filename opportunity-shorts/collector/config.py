from __future__ import annotations

import copy
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SETTINGS = {
    "user_agent": "UnemployerBot/0.1 (+mailto:you@example.com)",
    "db_path": "data/opportunities.db",
    "request_timeout": 25,
    "min_delay_seconds": 0.7,
    "max_description_chars": 6000,
    "filters": {
        "mode": "early_career",
        "india_only": True,
        "allow_global_remote": False,
        "include_title_keywords": [],
        "exclude_title_keywords": ["senior", "sr", "staff", "principal", "director", "head of",
                                   "vp", "vice president", "lead", "manager", "architect"],
        "min_description_chars": 80,
    },
    "priority_companies": [],
}


def load_yaml(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return default if data is None else data


def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings(config_dir: Path | str | None = None) -> dict:
    config_dir = Path(config_dir) if config_dir else ROOT / "config"
    settings = _deep_merge(DEFAULT_SETTINGS, load_yaml(config_dir / "settings.yaml", {}) or {})
    if os.environ.get("OPP_USER_AGENT"):
        settings["user_agent"] = os.environ["OPP_USER_AGENT"]
    if os.environ.get("OPP_DB_PATH"):
        settings["db_path"] = os.environ["OPP_DB_PATH"]
    db = Path(settings["db_path"])
    if not db.is_absolute():
        db = ROOT / db
    settings["db_path"] = str(db)
    return settings


def load_boards(config_dir: Path | str | None = None) -> list:
    config_dir = Path(config_dir) if config_dir else ROOT / "config"
    data = load_yaml(config_dir / "boards.yaml", {}) or {}
    return data.get("boards", []) or []


def load_sources_cfg(config_dir: Path | str | None = None) -> dict:
    config_dir = Path(config_dir) if config_dir else ROOT / "config"
    return load_yaml(config_dir / "sources.yaml", {}) or {}
