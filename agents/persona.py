"""Persona: rewrites each approved item for every viewer mode and language."""

from __future__ import annotations

from pathlib import Path

from .fact_checker import FactChecker
from .models import ModelClient
from .types import Facts, Moment

SYSTEM = (Path(__file__).parent / "prompts" / "persona.md").read_text(encoding="utf-8")
MODES = ("analyst", "casual", "player")


class Persona:
    name = "persona"

    def __init__(self, model: ModelClient, checker: FactChecker, languages: tuple[str, ...] = ("en", "es")):
        self.model = model
        self.checker = checker
        self.languages = languages

    async def render(self, moment: Moment, facts: Facts, approved: str) -> tuple[dict[str, dict[str, str]], list[str]]:
        """Returns ({lang: {mode: text}}, notes about anything that fell back to the approved text)."""
        out: dict[str, dict[str, str]] = {}
        notes: list[str] = []
        for lang in self.languages:
            out[lang] = {}
            for mode in MODES:
                prompt = f"Mode: {mode}. Language: {lang}.\nApproved text: {approved}\nFacts: {facts.values}"
                text = (await self.model.complete(
                    "persona", SYSTEM, prompt,
                    {"facts": facts.values, "kind": moment.kind, "mode": mode, "lang": lang, "approved": approved},
                )).strip()
                verdict = self.checker.check(text, facts)
                if not verdict.approved:
                    notes.append(f"{lang}/{mode}: {verdict.problems[0]}; kept the approved text")
                    text = approved
                out[lang][mode] = text
        return out, notes
