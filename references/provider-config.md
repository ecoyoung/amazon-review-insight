# Provider Configuration

## Goal

Support multiple LLM providers behind a single analysis workflow.

## Default Provider Order

1. `DeepSeek`
2. `Gemini`
3. `Qwen`
4. `MiniMax`

## Configuration Rules

- Never hardcode API keys.
- Never hardcode provider-specific credentials in source code.
- Keep runtime strategy separate from provider registry and separate both from real secrets.
- Read real API keys from environment variables only.
- Keep provider selection separate from prompt content.
- Assume the installing user provides the provider credentials in their own shell environment.
- Treat missing API credentials as a setup error, not a reason to fall back to embedded defaults.

## Recommended Three-Layer Model

### 1. Runtime Config

The runtime config should describe strategy only:

- default provider
- fallback order
- max reviews
- timeout
- retries
- optional model/base_url overrides

It should not store real API keys.

In normal operation, the project's built-in default runtime config should be
used. A custom runtime config is only needed for advanced overrides.

### 2. Provider Registry

The provider registry should describe reusable provider definitions:

- provider name
- default model
- default base URL
- API key env variable name
- optional model/base_url env variable names

Recommended files:

- [config/provider_registry.json](../config/provider_registry.json)
- [config/provider_registry.example.json](../config/provider_registry.example.json)
- [config/provider_registry.schema.json](../config/provider_registry.schema.json)

### 3. Environment Variables

Real secrets should only live in environment variables such as:

- `DEEPSEEK_API_KEY`
- `MINIMAX_API_KEY`
- `GEMINI_API_KEY`
- `QWEN_API_KEY`

## Recommended Config Pattern

Use:

- a runtime config for strategy
- a provider registry for shared provider definitions
- environment variables for real credentials

Example:

```json
{
  "analysis": {
    "default_provider": "deepseek",
    "fallback_order": ["deepseek", "minimax"]
  },
  "provider_registry_path": "./config/provider_registry.json",
  "provider_overrides": {
    "deepseek": {
      "model": "deepseek-v4-flash"
    }
  }
}
```

See [config/runtime_config.example.json](../config/runtime_config.example.json).

## Suggested Runtime Behavior

- use `DeepSeek` by default
- allow explicit override by the user or config
- retry once on transient provider failure
- if the active provider fails, automatically fall back through the configured provider order
- if all configured providers fail, stop and report the provider failure chain clearly

## Recommended Validation

Before a new user relies on the workflow, the installing environment should run:

```bash
.venv/bin/python scripts/check_env.py path/to/runtime_config.json
```

This confirms:

- dependencies are installed
- at least one provider is fully configured
- required assets are present
- runtime strategy and provider registry can resolve to a runnable provider

In normal use, Claude should handle the analysis workflow after the environment is already validated.
