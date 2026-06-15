# Distribution And Installation

This skill is meant to be shared without any embedded API credentials.

## Packaging Rules

Share the skill as a folder containing only the skill resources:

- `SKILL.md`
- `agents/`
- `scripts/`
- `config/`
- `references/`
- `logo.png`

Do not share:

- `.venv/`
- `output/`
- test data files
- any real `.env` file with secrets

## Recommended Share List

If you are preparing a repo or zip for another Claude Code user, keep:

- `SKILL.md`
- `agents/openai.yaml`
- `scripts/preprocess.py`
- `scripts/llm_analysis.py`
- `scripts/generate_report.py`
- `scripts/check_env.py`
- `scripts/run_pipeline.py`
- `config/`
- `references/`
- `logo.png`
- `.gitignore`

## Recommended Exclude List

Do not distribute these local or generated artifacts:

- `.venv/`
- `output/`
- `__pycache__/`
- real API keys or real `.env` files
- local test spreadsheets such as `Creatine powder.xlsx`
- any other customer or internal review exports

## Optional Repo Hygiene

The included `.gitignore` is designed to keep local environments, generated outputs, and test spreadsheets out of the shared skill package by default.

## Installation In Another Claude Code Environment

1. Copy or clone the skill folder into the recipient's skills directory.
2. Ensure the skill folder name remains stable, such as `amazon-review-insight`.
3. The recipient should create their own local environment variables for at least one provider.
4. The recipient should install Python dependencies in their own environment.
5. The recipient should prepare a runtime config JSON file.
6. The recipient should run the environment checker before their first analysis run.

This installation work happens once per machine. After that, the normal user experience should be skill-driven inside Claude, not command-driven in a shell.

## One-Time Setup Commands

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pandas openpyxl openai
.venv/bin/python scripts/check_env.py config/runtime_config.example.json
```

## Provider Setup Model

The skill must never ship with active credentials.

The user who installs the skill should provide their own variables, for example:

```bash
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
export DEEPSEEK_MODEL="deepseek-v4-flash"
export DEEPSEEK_API_KEY="..."
```

They may instead choose Gemini, Qwen, or MiniMax.

They should then create a runtime config file based on:

- `config/runtime_config.example.json`

## Claude Usage Model

After setup, the intended usage is:

1. the user activates or invokes the skill in Claude
2. the user provides a review file
3. the user provides a runtime config file
4. Claude runs the skill's internal scripts automatically
5. Claude returns the generated report and supporting files

The user should not need to manually run `preprocess.py`, `llm_analysis.py`, or `generate_report.py` during normal skill use.

## Minimum Shareable Explanation

When handing this skill to another user, explain:

- this skill does not include any API key
- they must provide their own provider environment variables
- they should provide both a review file and a runtime config file
- Claude should run the workflow automatically once the skill is installed and configured
- `scripts/check_env.py` is only for setup validation or troubleshooting

For a fuller non-technical walkthrough, share:

- [usage-guide.md](usage-guide.md)
