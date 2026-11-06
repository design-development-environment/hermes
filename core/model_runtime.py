#!/usr/bin/env python3
"""Private runtime configuration for replaceable Hermes model providers."""

from __future__ import annotations

import copy
import json
import os
import re
import sqlite3
import tempfile
import urllib.parse
from contextlib import closing
from pathlib import Path
from platform_support import CONFIG_DIR, openwebui_data_dir


CONFIG_PATH = CONFIG_DIR / "models.json"
OPENWEBUI_DB = openwebui_data_dir() / "webui.db"
MODEL_NAME = re.compile(r"^[A-Za-z0-9._:/@+-]{1,200}$")
PROVIDER_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
DEFAULT_CONFIG = {
    "version": 2,
    "vision": {
        "provider": "nvidia",
        "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
    },
    "providers": {
        "openai_compatible": {
            "type": "openai_compatible",
            "base_url": "https://api.openai.com/v1",
            "api_key_env": "HERMES_VISION_API_KEY",
            "enabled": False,
        },
        "nvidia": {
            "type": "openai_compatible",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "credential_source": "openwebui",
            "enabled": True,
        },
    },
}


def _validate_url(value: str) -> str:
    value = value.rstrip("/")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme == "https" and parsed.netloc:
        return value
    raise ValueError("Cloud provider URL must use HTTPS")


def validate_config(config: dict) -> dict:
    if not isinstance(config, dict):
        raise ValueError("Model configuration must be an object")
    result = copy.deepcopy(DEFAULT_CONFIG)
    result.update({key: value for key, value in config.items() if key not in {"vision", "providers"}})
    result["vision"] = {**DEFAULT_CONFIG["vision"], **(config.get("vision") or {})}
    result["providers"] = copy.deepcopy(DEFAULT_CONFIG["providers"])
    result["providers"].update(config.get("providers") or {})

    provider_name = result["vision"].get("provider", "")
    model_name = result["vision"].get("model", "")
    if not PROVIDER_NAME.fullmatch(provider_name):
        raise ValueError("Invalid vision provider name")
    if not MODEL_NAME.fullmatch(model_name):
        raise ValueError("Invalid vision model name")
    if provider_name not in result["providers"]:
        raise ValueError(f"Unknown vision provider: {provider_name}")

    for name, provider in result["providers"].items():
        if not PROVIDER_NAME.fullmatch(name) or not isinstance(provider, dict):
            raise ValueError("Invalid provider configuration")
        provider_type = provider.get("type")
        if provider_type != "openai_compatible":
            raise ValueError(f"Unsupported provider type: {provider_type}")
        provider["base_url"] = _validate_url(provider.get("base_url", ""))
        key_env = provider.get("api_key_env", "")
        credential_source = provider.get("credential_source", "env")
        if credential_source not in {"env", "openwebui"}:
            raise ValueError("Unsupported cloud credential source")
        if credential_source == "env" and not re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", key_env):
            raise ValueError("Cloud provider api_key_env must be an environment-variable name")
        provider["enabled"] = bool(provider.get("enabled", False))
    return result


def save_config(config: dict) -> dict:
    validated = validate_config(config)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=CONFIG_DIR, prefix="models-", suffix=".tmp", delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(validated, handle, indent=2)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, CONFIG_PATH)
    finally:
        temporary.unlink(missing_ok=True)
    return validated


def load_config() -> dict:
    if not CONFIG_PATH.is_file():
        return save_config(DEFAULT_CONFIG)
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    # One-time migration from the former local Ollama/Moondream runtime.
    if raw.get("vision", {}).get("provider") == "ollama" or "ollama" in raw.get("providers", {}):
        raw["vision"] = copy.deepcopy(DEFAULT_CONFIG["vision"])
        raw["providers"] = {
            name: provider for name, provider in raw.get("providers", {}).items() if name != "ollama"
        }
        raw["version"] = DEFAULT_CONFIG["version"]
        return save_config(raw)
    return validate_config(raw)


def resolve_vision(provider: str = "", model: str = "") -> dict:
    config = load_config()
    provider_name = provider.strip() or config["vision"]["provider"]
    model_name = model.strip() or config["vision"]["model"]
    if not PROVIDER_NAME.fullmatch(provider_name) or provider_name not in config["providers"]:
        raise ValueError(f"Unknown vision provider: {provider_name}")
    if not MODEL_NAME.fullmatch(model_name):
        raise ValueError("Invalid vision model name")
    provider_config = config["providers"][provider_name]
    if provider_config["type"] == "openai_compatible":
        if not provider_config.get("enabled"):
            raise RuntimeError("Cloud vision is disabled in Hermes model configuration")
        provider_api_key(provider_config)
    return {"provider": provider_name, "model": model_name, **provider_config}


def _openwebui_api_key(base_url: str) -> str:
    if not OPENWEBUI_DB.is_file():
        return ""
    with closing(sqlite3.connect(OPENWEBUI_DB, timeout=5)) as db, db:
        rows = dict(db.execute(
            "SELECT key,value FROM config WHERE key IN ('openai.api_base_urls','openai.api_keys')"
        ).fetchall())
    try:
        urls = json.loads(rows.get("openai.api_base_urls", "[]"))
        keys = json.loads(rows.get("openai.api_keys", "[]"))
    except json.JSONDecodeError:
        return ""
    normalized = base_url.rstrip("/")
    for index, url in enumerate(urls):
        if str(url).rstrip("/") == normalized and index < len(keys):
            return str(keys[index]).strip()
    return ""


def provider_api_key(provider: dict) -> str:
    if provider.get("credential_source", "env") == "openwebui":
        key = _openwebui_api_key(provider["base_url"])
        location = "the matching Open WebUI connection"
    else:
        key_name = provider.get("api_key_env", "")
        key = os.environ.get(key_name, "").strip()
        location = key_name
    if not key:
        raise RuntimeError(f"Cloud provider API key is not configured in {location}")
    return key


def configure_vision(provider: str, model: str, *, base_url: str = "", enabled: bool | None = None, confirmed: bool = False) -> dict:
    if not confirmed:
        raise PermissionError("Changing the default vision provider requires explicit confirmation")
    config = load_config()
    if provider not in config["providers"]:
        raise ValueError(f"Unknown vision provider: {provider}")
    provider_config = config["providers"][provider]
    if base_url:
        provider_config["base_url"] = _validate_url(base_url)
    if enabled is not None:
        provider_config["enabled"] = bool(enabled)
    config["vision"] = {"provider": provider, "model": model}
    saved = save_config(config)
    return public_status(saved)


def public_status(config: dict | None = None) -> dict:
    config = config or load_config()
    providers = {}
    for name, provider in config["providers"].items():
        item = {
            "type": provider["type"],
            "base_url": provider["base_url"],
            "enabled": provider.get("enabled", True),
        }
        try:
            provider_api_key(provider)
            item["api_key_configured"] = True
        except RuntimeError:
            item["api_key_configured"] = False
        item["credential_source"] = provider.get("credential_source", "env")
        if provider.get("credential_source", "env") == "env":
            item["api_key_env"] = provider["api_key_env"]
        providers[name] = item
    return {
        "config_path": str(CONFIG_PATH),
        "vision": config["vision"],
        "providers": providers,
        "note": "Workspace presets can override vision provider/model per request without changing this default.",
    }
