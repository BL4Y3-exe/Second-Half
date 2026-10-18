"""Storyteller: writes why a moment matters, using only the Analyst's facts."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ModelClient
from .types import Draft, Facts, Moment

SYSTEM = (Path(__file__).parent / "prompts" / "storyteller.md").read_text(encoding="utf-8")


class Storyteller:
    name = "storyteller"

    def __init__(self, model: ModelClient):
        self.model = model

    async def write(self, moment: Moment, facts: Facts, attempt: int, feedback: list[str] | None = None) -> Draft:
        # No clock: "42:58" would put two numbers in the story that aren't facts (the minute is one).
        facts_json = json.dumps(facts.for_model(), ensure_ascii=False)
        prompt = f"Moment: {moment.label} ({moment.kind}).\nFacts: {facts_json}\n"
        if feedback:
            prompt += "Your last draft was rejected by the fact-checker:\n- " + "\n- ".join(feedback) + "\n"
        text = await self.model.complete(
            "storyteller", SYSTEM, prompt,
            {"facts": facts.values, "kind": moment.kind, "clock": moment.clock, "attempt": attempt,
             "feedback": feedback or []},
        )
        return Draft(moment.id, text.strip(), attempt)
