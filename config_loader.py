"""config_loader.py - load config.yaml (personal, git-ignored) or fall back to config.example.yaml."""

import os
import yaml

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PERSONAL = os.path.join(BASE_DIR, "config.yaml")
EXAMPLE = os.path.join(BASE_DIR, "config.example.yaml")


class ConfigError(Exception):
    pass


def resolve_path(path: str = None) -> str:
    if path:
        if not os.path.exists(path):
            raise ConfigError(f"Config file not found: {path}")
        return path
    for candidate in (PERSONAL, EXAMPLE):
        if os.path.exists(candidate):
            return candidate
    raise ConfigError("No config.yaml or config.example.yaml found next to main.py")


def load_config(path: str = None) -> dict:
    """Load YAML config; returns a dict (never None). Raises ConfigError on bad input."""
    resolved = resolve_path(path)
    try:
        with open(resolved, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {resolved}: {e}")
    if not isinstance(cfg, dict):
        raise ConfigError(f"{resolved} must contain a YAML mapping")
    cfg["_path"] = resolved
    return cfg
