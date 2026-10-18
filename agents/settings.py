"""Which model the writing agents use, from environment variables or a .env file.

Set FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL to run on Microsoft Foundry.
With neither set, everything runs on the scripted mock model.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path = ROOT / ".env") -> None:
    """Reads KEY=value lines from a .env file. Variables already set in the environment win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def foundry_settings() -> dict[str, str] | None:
    """The Foundry project endpoint and model deployment, or None when they aren't both set."""
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    model = os.environ.get("FOUNDRY_MODEL", "").strip()
    if not endpoint or not model:
        return None
    return {
        "endpoint": endpoint,
        "model": model,
        # gpt-5 family models think before answering; "low" keeps live stories quick. "" turns it off,
        # which models without reasoning (such as gpt-4.1-mini) need.
        "reasoning_effort": os.environ.get("FOUNDRY_REASONING_EFFORT", "low").strip(),
    }
