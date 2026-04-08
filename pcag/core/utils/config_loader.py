"""
PCAG configuration loader.

Loads YAML files from config/ and supports ${ENV:default} substitution.
Also supports a lightweight local .env file convention for development.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
_cache: dict[str, dict] = {}


def load_dotenv_file(dotenv_path: str | None = None, *, override: bool = False) -> None:
    """
    Load a simple .env file into os.environ.

    Supported lines:
    - KEY=value
    - blank lines ignored
    - # comments ignored
    """
    path = Path(dotenv_path or os.path.join(PROJECT_ROOT, ".env"))
    if not path.exists():
        return

    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if not key:
                continue
            if override or key not in os.environ:
                os.environ[key] = value
    except Exception as exc:
        logger.warning("Failed to load .env file %s: %s", path, exc)


def load_config(filename: str, required: bool = False) -> dict:
    if filename in _cache:
        return _cache[filename]

    filepath = os.path.join(CONFIG_DIR, filename)
    if not os.path.exists(filepath):
        if required:
            logger.critical("[FAIL-HARD] Config file missing: %s", filepath)
            raise FileNotFoundError(f"Required config file not found: {filepath}")
        logger.warning("Config file not found: %s, returning empty dict", filepath)
        return {}

    try:
        with open(filepath, "r", encoding="utf-8") as handle:
            content = handle.read()
            data = yaml.safe_load(content) or {}

        data = _substitute_env_vars(data)
        _cache[filename] = data
        logger.info("Config loaded: %s", filepath)
        return data
    except Exception as exc:
        logger.critical("[FAIL-HARD] Config parse error in %s: %s", filepath, exc)
        raise


def load_required_config(filename: str) -> dict:
    return load_config(filename, required=True)


def _substitute_env_vars(data):
    if isinstance(data, dict):
        return {k: _substitute_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_substitute_env_vars(v) for v in data]
    if isinstance(data, str):
        def replace(match):
            var_name = match.group(1)
            default_val = match.group(2) if match.group(2) is not None else ""
            return os.environ.get(var_name, default_val)

        pattern = r"\$\{([^}:]+)(?::([^}]*))?\}"
        return re.sub(pattern, replace, data)
    return data


def get_service_urls() -> dict:
    config = load_config("services.yaml")
    services = config.get("services", {})
    return {name: svc.get("url", "") for name, svc in services.items()}


def get_sensor_mappings() -> dict:
    return load_config("sensor_mappings.yaml")


def get_cbf_mappings() -> list:
    config = load_config("cbf_mappings.yaml")
    return config.get("mappings", [])


def clear_cache():
    _cache.clear()


def get_auth_config() -> dict:
    config = load_config("services.yaml")
    return config.get("auth", {})


def get_benchmark_runtime_config() -> dict:
    config = load_config("services.yaml")
    return config.get("benchmark_runtime", {})


load_dotenv_file()
