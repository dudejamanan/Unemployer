from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

from collector.config import ROOT, load_yaml

DEFAULT_SHORTS_SETTINGS = {
    "llm": {
        "provider": "ollama",
        "base_url": "http://127.0.0.1:11434",
        "model": "qwen3:8b",
        "temperature": 0.6,
        "max_retries": 2,
        "timeout_seconds": 300,
        "fallback_on_failure": False,
        "num_ctx": 4096,
        "num_gpu": 0,
    },
    "automation": {"enabled": False, "max_builds_per_run": 3, "interval_minutes": 30,
                   "collection_interval_minutes": 15, "publishing_mode": "slots"},
    "voices": {
        "male": "en-IN-PrabhatNeural",
        "female": "en-IN-NeerjaNeural",
        "alternate": True,
    },
    "script": {
        "min_words": 55,
        "max_words": 85,
        "target_duration_seconds": 25,
        "max_title_chars": 100,
        "hinglish_enabled": False,
    },
    "theme": {
        "safe_zone_bottom_percent": 22,
        "safe_zone_right_percent": 12,
        "min_font_size": 56,
        "max_words_per_line": 7,
        "color_schemes": [
            {
                "name": "blue",
                "primary": "#1a365d",
                "secondary": "#2b6cb0",
                "accent": "#4299e1",
                "text": "#ffffff",
                "background": "#f7fafc",
            },
            {
                "name": "purple",
                "primary": "#44337a",
                "secondary": "#6b46c1",
                "accent": "#9f7aea",
                "text": "#ffffff",
                "background": "#faf5ff",
            },
        ],
    },
    "upload": {
        "daily_limit": 3,
        "ist_slots": ["08:00", "13:00", "19:00"],
        "category_id": 27,
        "made_for_kids": False,
    },
    "paths": {
        "output_dir": "out",
        "assets_dir": "assets",
        "fonts_dir": "assets/fonts",
        "music_dir": "assets/music",
    },
    "assembly": {
        "fps": 30,
        "width": 1080,
        "height": 1920,
        "crf": 20,
        "preset": "medium",
        "audio_bitrate": "192k",
        "min_duration": 20,
        "max_duration": 40,
        # Music is statically attenuated this many dB below the voice.
        # Clamped to [-22, -18] at assembly time (M4 requirement).
        "music_duck_db": -20,
        "min_scene_seconds": 0.6,
    },
    "captions": {
        "font": "Inter",
        "font_size": 64,
        "max_words": 4,
        "max_gap_seconds": 0.6,
        "uppercase": True,
        # Bottom 22% of 1920px is reserved for YouTube UI overlays,
        # so captions must sit at least ~422px above the bottom edge.
        "margin_bottom": 440,
        "margin_side": 140,
        "outline": 4,
    },
}


def _load_dotenv(root: Path) -> None:
    """Parse .env into os.environ (existing env vars win). No third-party dep."""
    env_path = root / ".env"
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError as e:  # pragma: no cover - defensive
        import logging
        logging.getLogger(__name__).warning("Could not read .env: %s", e)


def load_shorts_settings(config_dir: Path | str | None = None) -> dict[str, Any]:
    """Load shorts.yaml, merge with defaults, override with env vars."""
    _load_dotenv(ROOT)
    config_dir = Path(config_dir) if config_dir else ROOT / "config"
    # Deep copy so deep-merging YAML never mutates the module-level defaults.
    settings = copy.deepcopy(DEFAULT_SHORTS_SETTINGS)

    # Load from YAML if exists
    yaml_path = config_dir / "shorts.yaml"
    if yaml_path.exists():
        yaml_cfg = load_yaml(yaml_path)
        _deep_merge(settings, yaml_cfg)

    # Override with env vars
    for environment, key in (("OLLAMA_BASE_URL", "base_url"), ("OLLAMA_MODEL", "model")):
        if os.getenv(environment):
            settings["llm"][key] = os.environ[environment]
    settings["youtube_client_secrets_file"] = os.getenv(
        "YOUTUBE_CLIENT_SECRETS_FILE", str(ROOT / "secrets" / "client_secret.json"))
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        settings["telegram_bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN")
    if os.getenv("TELEGRAM_CHANNEL_ID"):
        settings["telegram_channel_id"] = os.getenv("TELEGRAM_CHANNEL_ID")

    settings["youtube_token_file"] = os.getenv("YOUTUBE_TOKEN_FILE", str(ROOT / "secrets" / "youtube_token.json"))
    for key in ("youtube_token_file", "youtube_client_secrets_file"):
        if settings.get(key) and not Path(settings[key]).is_absolute():
            settings[key] = str(ROOT / settings[key])
    # Resolve paths relative to project root
    for key in ["output_dir", "assets_dir", "fonts_dir", "music_dir"]:
        if key in settings["paths"]:
            p = settings["paths"][key]
            if not Path(p).is_absolute():
                settings["paths"][key] = str(ROOT / p)

    return settings


def _deep_merge(base: dict, update: dict) -> None:
    """Recursively merge update dict into base dict (in-place)."""
    for key, value in update.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
