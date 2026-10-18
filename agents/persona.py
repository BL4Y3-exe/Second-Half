"""Persona: rewrites each approved item for every viewer mode and language."""

from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path

from . import templates
from .fact_checker import FactChecker
from .models import ModelClient, explain_failure
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
        """Returns ({lang: {mode: text}}, notes about anything that fell back to a scripted line).

        All versions are written at once. One that fails fact-checking, or whose model call fails, falls back
        to the scripted line for that mode and language, which is built from the facts alone."""
        jobs = [(lang, mode) for lang in self.languages for mode in MODES]
        results = await asyncio.gather(*(self._one(moment, facts, approved, lang, mode) for lang, mode in jobs))
        out: dict[str, dict[str, str]] = {lang: {} for lang in self.languages}
        notes: list[str] = []
        for (lang, mode), (text, note) in zip(jobs, results, strict=True):
            out[lang][mode] = text
            if note:
                notes.append(f"{lang}/{mode}: {note}")
        return out, notes

    async def _one(self, moment: Moment, facts: Facts, approved: str, lang: str, mode: str) -> tuple[str, str | None]:
        context = {"facts": facts.values, "kind": moment.kind, "clock": moment.clock, "mode": mode, "lang": lang,
                   "approved": approved}
        if lang == "en" and mode == "analyst":
            return approved, None  # the Storyteller already wrote it for this viewer, and it passed fact-checking
        prompt = (f"Mode: {mode}. Language: {lang}.\nApproved text: {approved}\n"
                  f"Facts: {json.dumps(facts.for_model(), ensure_ascii=False)}")
        try:
            text = (await self.model.complete("persona", SYSTEM, prompt, context)).strip()
        except Exception as exc:  # any model failure (timeout, quota, network) falls back the same way
            return self._scripted(context), f"{explain_failure(exc)}; used the scripted line"
        verdict = self.checker.check(text, facts)
        if not verdict.approved:
            return self._scripted(context), f"{verdict.problems[0]}; used the scripted line"
        return text, None

    @staticmethod
    def _scripted(context: dict) -> str:
        return templates.persona(context, random.Random(f"{context['clock']}|{context['mode']}|{context['lang']}"))
