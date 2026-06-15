#!/usr/bin/env python3
"""
Environment checker for Amazon Review Insight.

This script verifies:
- Python dependencies
- available LLM provider environment variables
- presence of brand assets

It never prints full API keys.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from provider_registry import (
    load_runtime_config,
    ordered_providers,
    resolve_provider_settings,
)


DEPENDENCIES = ["pandas", "openpyxl", "langchain_openai", "langchain_core"]
def module_status(name: str) -> tuple[bool, str]:
    try:
        importlib.import_module(name)
        return True, "installed"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def masked_key(value: str) -> str:
    if not value:
        return "(missing)"
    if len(value) <= 8:
        return "********"
    return f"{value[:4]}...{value[-4:]}"


def provider_status(name: str, runtime_config: dict | None = None) -> dict[str, str | bool]:
    runtime_config = runtime_config or {}
    settings = resolve_provider_settings(name, runtime_config=runtime_config)
    base_url = settings["base_url"]
    model = settings["model"]
    api_key = settings["api_key"]
    configured = bool(base_url and model and api_key)
    return {
        "configured": configured,
        "base_url": base_url or "(missing)",
        "model": model or "(missing)",
        "api_key": masked_key(api_key),
        "api_key_env": settings["api_key_env"] or "(missing)",
    }

def main() -> None:
    runtime_config = {}
    if len(sys.argv) > 1:
        runtime_config = load_runtime_config(sys.argv[1])
    print("== Amazon Review Insight Environment Check ==")
    print("")
    print("Dependencies:")
    for dep in DEPENDENCIES:
        ok, detail = module_status(dep)
        marker = "OK" if ok else "MISSING"
        print(f"- {dep}: {marker} ({detail})")

    print("")
    print("Providers:")
    configured_count = 0
    for provider in ordered_providers(runtime_config):
        status = provider_status(provider, runtime_config)
        if status["configured"]:
            configured_count += 1
        print(f"- {provider}: {'configured' if status['configured'] else 'incomplete'}")
        print(f"  base_url: {status['base_url']}")
        print(f"  model: {status['model']}")
        print(f"  api_key: {status['api_key']}")
        print(f"  api_key_env: {status['api_key_env']}")

    print("")
    root = Path(__file__).resolve().parents[1]
    logo_path = root / "logo.png"
    print("Assets:")
    print(f"- logo.png: {'found' if logo_path.exists() else 'missing'}")

    print("")
    if configured_count == 0:
        print("Result: no usable LLM providers are configured yet.")
    else:
        print(f"Result: {configured_count} provider(s) look runnable.")


if __name__ == "__main__":
    main()
