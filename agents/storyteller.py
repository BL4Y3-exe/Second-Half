"""Storyteller: writes why a moment matters, using only the Analyst's facts."""

from __future__ import annotations

from pathlib import Path

from .models import ModelClient
from .types import Draft, Facts, Moment

SYSTEM = (Path(__file__).parent / "prompts" / "storyteller.md").read_text(encoding="utf-8")


class Storyteller:
    name = "storyteller"

    def __init__(self, model: ModelClient):
        self.model = model

    async def write(self, moment: Moment, facts: Facts, attempt: int, feedback: list[str] | None = None) -> Draft:
        prompt = f"Moment: {moment.label} ({moment.kind}, {moment.clock}).\nFacts: {facts.values}\n"
        if feedback:
            prompt += "Your last draft was rejected by the fact-checker:\n- " + "\n- ".join(feedback) + "\n"
        text = await self.model.complete(
            "storyteller", SYSTEM, prompt,
            {"facts": facts.values, "kind": moment.kind, "attempt": attempt, "feedback": feedback or []},
        )
        return Draft(moment.id, text.strip(), attempt)
