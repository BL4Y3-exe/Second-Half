"""Model clients. Agents talk to a model through `ModelClient.complete`.

`MockModel` runs everything locally with scripted, realistic text so the
whole studio works without Azure. `FoundryModel` (agents/foundry.py) writes
with a model deployed in Microsoft Foundry, behind the same interface.
"""

from __future__ import annotations

import functools
import random
from typing import Protocol

from . import templates
from .settings import foundry_settings


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


@functools.cache
def _foundry(endpoint: str, model: str, reasoning_effort: str) -> ModelClient:
    from .foundry import FoundryModel  # only needs the Azure packages when Foundry is configured

    return FoundryModel(endpoint, model, reasoning_effort)


def load_model(seed: int = 0, use: str = "auto") -> ModelClient:
    """The model the writing agents use. "auto" picks Foundry when FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL
    are set, the scripted mock otherwise. Every match shares one Foundry client; each gets its own mock."""
    settings = foundry_settings()
    if use == "foundry" and settings is None:
        raise ValueError("set FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL (in the environment or .env) to use Foundry")
    if use == "mock" or settings is None:
        return MockModel(seed=seed)
    return _foundry(settings["endpoint"], settings["model"], settings["reasoning_effort"])


def _root_cause(exc: BaseException) -> BaseException:
    """Agent Framework wraps the real error (a sign-in or HTTP failure); dig it out."""
    seen: set[int] = set()
    while id(exc) not in seen:
        seen.add(id(exc))
        inner = next((a for a in exc.args if isinstance(a, BaseException)), None) or exc.__cause__
        if inner is None:
            break
        exc = inner
    return exc


def explain_failure(exc: BaseException) -> str:
    """A short reason a model call failed, with what to check when it is a set-up problem."""
    if isinstance(exc, TimeoutError):
        return "the model took too long to answer"
    root = _root_cause(exc)
    name = type(root).__name__
    detail = (str(root).splitlines() or [""])[0][:140]
    status = getattr(root, "status_code", None)
    if name in ("CredentialUnavailableError", "ClientAuthenticationError"):
        return f"can't sign in to Azure ({detail}); run az login"
    if status in (401, 403):
        return f"Foundry refused the sign-in ({status}); the account needs the Foundry User role on the resource"
    if status == 404:
        return "Foundry answered 404; check FOUNDRY_MODEL is the deployment name and the endpoint is the project's"
    if status == 429:
        return "Foundry rate limit (429): the deployment's tokens-per-minute quota is used up for now"
    if status == 400 and "reasoning" in detail.lower():
        return "this model doesn't take a reasoning effort; set FOUNDRY_REASONING_EFFORT= (empty)"
    if name == "APIConnectionError":
        return "can't reach Foundry; check FOUNDRY_PROJECT_ENDPOINT"
    return f"model call failed: {name}" + (f" ({detail})" if detail else "")
