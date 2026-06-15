"""Backend package for Amazon Review Insight.

Adds the project ``scripts/`` directory to ``sys.path`` so both the API
process (uvicorn) and the RQ worker process can import modules such as
``run_multi_agent_workflow`` and ``provider_registry``. Without this, jobs
queued from the web UI fail with ``ModuleNotFoundError`` inside the worker.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT_DIR = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _ROOT_DIR / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
