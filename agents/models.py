"""Model clients. Agents talk to a model through `ModelClient.complete`.

`MockModel` runs everything locally with scripted, realistic text so the
whole studio works without Azure keys. A Microsoft Foundry client plugs in
behind the same interface.
"""

from __future__ import annotations

import random
from typing import Protocol

from . import templates


class ModelClient(Protocol):
    name: str

    async def complete(self, agent: str, system: str, prompt: str, context: dict) -> str: ...


class MockModel:
    """Scripted writer. With `mistake_rate` > 0 the Storyteller sometimes gets a number wrong on its
    first draft, the way a real model can, so the Fact-checker's retry loop is visible in demos."""

    name = "mock"

    def __init__(self, seed: int = 0, mistake_rate: float = 0.2):
        self.rng = random.Random(seed)
        self.mistake_rate = mistake_rate

    async def complete(self, agent: str, system: str, prompt: str, context: dict) -> str:
        if agent == "storyteller":
            return templates.story(context, self.rng, allow_mistake=context.get("attempt", 1) == 1
                                   and self.rng.random() < self.mistake_rate)
        if agent == "persona":
            return templates.persona(context, self.rng)
        if agent == "recap":
            return templates.recap(context, self.rng)
        raise ValueError(f"mock model has no script for agent {agent!r}")
