#!/usr/bin/env python3
"""Provider registry helpers for amazon-review-insight."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


FALLBACK_CHAIN: list[str] = ["deepseek", "gemini", "qwen", "minimax"]
DEFAULT_PROVIDER_ORDER = FALLBACK_CHAIN
_ENV_LOADED = False


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_local_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    env_path = project_root() / ".env"
    if not env_path.exists():
        _ENV_LOADED = True
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value

    _ENV_LOADED = True


def load_runtime_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    file_path = Path(path).expanduser()
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_provider_registry(path: str | None = None) -> dict[str, Any]:
    registry_path = (
        Path(path).expanduser()
        if path
        else project_root() / "config" / "provider_registry.json"
    )
    if not registry_path.exists():
        registry_path = project_root() / "config" / "provider_registry.example.json"
    with open(registry_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_provider_settings(
    provider_name: str,
    *,
    registry: dict[str, dict[str, str]] | None = None,
    runtime_config: dict[str, Any] | None = None,
    model_override: str | None = None,
) -> dict[str, str]:
    load_local_env()
    runtime_config = runtime_config or {}
    provider = provider_name.lower()
    registry_data = registry or load_provider_registry()
    providers = registry_data.get("providers", registry_data)
    entry = providers.get(provider, {}) or {}
    overrides = (runtime_config.get("provider_overrides", {}) or {}).get(provider, {}) or {}

    upper = provider.upper()
    api_key_env = str(
        overrides.get("api_key_env") or entry.get("api_key_env") or f"{upper}_API_KEY"
    )
    base_url_env = str(
        overrides.get("base_url_env") or entry.get("base_url_env") or f"{upper}_BASE_URL"
    )
    model_env = str(
        overrides.get("model_env") or entry.get("model_env") or f"{upper}_MODEL"
    )

    base_url = str(
        overrides.get("base_url")
        or os.getenv(base_url_env, "").strip()
        or entry.get("base_url", "")
        or ""
    ).strip()
    model = str(
        model_override
        or overrides.get("model")
        or os.getenv(model_env, "").strip()
        or entry.get("model", "")
        or ""
    ).strip()
    api_key = os.getenv(api_key_env, "").strip()

    return {
        "name": provider,
        "base_url": base_url,
        "model": model,
        "api_key": api_key,
        "api_key_env": api_key_env,
        "base_url_env": base_url_env,
        "model_env": model_env,
    }


def ordered_providers(
    runtime_config: dict[str, Any] | None = None,
    provider_override: str | None = None,
) -> list[str]:
    runtime_config = runtime_config or {}
    analysis_cfg = runtime_config.get("analysis", {}) or {}
    configured = [str(item).lower() for item in analysis_cfg.get("fallback_order", FALLBACK_CHAIN)]
    default_provider = str(analysis_cfg.get("default_provider", "")).strip().lower()
    if default_provider:
        configured = [default_provider, *[item for item in configured if item != default_provider]]
    if provider_override:
        provider = provider_override.lower()
        configured = [provider, *[item for item in configured if item != provider]]
    deduped: list[str] = []
    for item in configured:
        if item and item not in deduped:
            deduped.append(item)
    return deduped or list(FALLBACK_CHAIN)


def resolve_registry_path(runtime_config: dict[str, Any] | None = None) -> str | None:
    override = (runtime_config or {}).get("provider_registry")
    if override:
        return str(Path(str(override)).expanduser())
    return str(project_root() / "config" / "provider_registry.json")
