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
    first draft, the way a real model can, so the Fact-checker's retry loop is visible in demos. The first
    goal's first draft always slips, so a demo always shows a catch.

    Every choice is seeded by the match seed and the moment itself (kind and clock), so the same match
    gets the same stories however fast it is played or sampled."""

    name = "mock"

    def __init__(self, seed: int = 0, mistake_rate: float = 0.2):
        self.seed = seed
        self.mistake_rate = mistake_rate
        self._goals_written: set[str] = set()

    def _rng(self, context: dict, *salt: object) -> random.Random:
        return random.Random(f"{self.seed}|{context.get('kind')}|{context.get('clock')}|" + "|".join(map(str, salt)))

    async def complete(self, agent: str, system: str, prompt: str, context: dict) -> str:
        if agent == "storyteller":
            attempt = context.get("attempt", 1)
            rng = self._rng(context, "story", attempt)
            first_goal = context.get("kind") == "goal" and not self._goals_written
            if context.get("kind") == "goal":
                self._goals_written.add(str(context.get("clock")))
            slip = attempt == 1 and (first_goal or rng.random() < self.mistake_rate)
            return templates.story(context, rng, allow_mistake=slip and self.mistake_rate > 0)
        if agent == "persona":
            return templates.persona(context, self._rng(context, "persona", context.get("mode"), context.get("lang")))
        if agent == "recap":
            return templates.recap(context, self._rng(context, "recap", context.get("lang")))
        raise ValueError(f"mock model has no script for agent {agent!r}")
