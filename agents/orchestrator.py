"""Runs the studio team: shared match state, explicit handoffs, retries and fallbacks.

Spotter -> Analyst -> Storyteller <-> Fact-checker (max 2 retries) -> Director -> Persona -> viewers.
Half time and full time go to the Recap agent. Every handoff is published as
a trace step so the app can show the team at work.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from mcp_server import MatchTools
from stats import MatchState

from . import templates
from .analyst import Analyst
from .director import Director
from .fact_checker import FactChecker
from .models import MockModel, ModelClient
from .persona import MODES, Persona
from .recap import Recap
from .spotter import Spotter
from .storyteller import Storyteller
from .types import Moment, TraceStep

Publish = Callable[[str, dict], None]
MAX_RETRIES = 2


class Orchestrator:
    def __init__(self, state: MatchState, publish: Publish, speed: float = 10.0, model: ModelClient | None = None,
                 languages: tuple[str, ...] = ("en", "es"), seed: int = 0):
        self.state = state
        self.publish = publish
        self.model = model or MockModel(seed=seed)
        self.tools = MatchTools(state)
        self.spotter = Spotter()
        self.analyst = Analyst(self.tools)
        self.storyteller = Storyteller(self.model)
        self.checker = FactChecker(state.players)
        self.director = Director(speed, self.tools)
        self.persona = Persona(self.model, self.checker, languages)
        self.recap = Recap(self.model, self.tools)
        self.languages = languages
        self.queue: asyncio.Queue[Moment] = asyncio.Queue()
        self.trace: list[dict] = []
        self.overlays: list[dict] = []
        self.stats = {"moments": 0, "approved_first_time": 0, "caught": 0, "fallbacks": 0, "dropped": 0}
        self._step = 0

    # --- input from the live match --------------------------------------------

    def observe(self, events: list[dict], triggers: list[dict], now: float) -> None:
        for tr in triggers:
            self.spotter.watch(tr)
        for moment, tr, reason in self.spotter.release(now):
            if moment is not None:
                self.queue.put_nowait(moment)
            elif tr["priority"] <= 2:
                self._trace(tr["t"], tr["clock"], tr["id"], "spotter", "passed over", f"{tr['label']} ({reason})",
                            status="skipped")
        for ev in events:
            if ev["type"] in ("half_time", "full_time"):
                label = "Half time" if ev["type"] == "half_time" else "Full time"
                self.queue.put_nowait(self.spotter.recap(label, ev["t"], ev["clock"]))

    def flush(self, now: float) -> None:
        """At full time: release anything the Spotter is still holding."""
        self.observe([], [], now + 10.0)

    async def run(self) -> None:
        while True:
            moment = await self.queue.get()
            await self.handle(moment)

    async def drain(self) -> None:
        while not self.queue.empty():
            await self.handle(self.queue.get_nowait())

    # --- the pipeline -------------------------------------------------------------

    async def handle(self, moment: Moment) -> dict | None:
        self.stats["moments"] += 1
        m = moment
        self._trace(m.t, m.clock, m.id, "spotter", "flagged", m.label, detail={"kind": m.kind, "priority": m.priority})
        if m.kind == "recap":
            return await self._handle_recap(m)

        started = time.perf_counter()
        facts = self.analyst.analyse(m)
        self._trace(m.t, m.clock, m.id, "analyst", "looked up",
                    f"{len(facts.tool_calls)} tool calls, {len(facts.numbers())} numbers",
                    ms=self._ms(started), detail={"tool_calls": facts.tool_calls, "facts": facts.values})

        approved: str | None = None
        feedback: list[str] | None = None
        for attempt in range(1, MAX_RETRIES + 2):
            started = time.perf_counter()
            draft = await self.storyteller.write(m, facts, attempt, feedback)
            self._trace(m.t, m.clock, m.id, "storyteller", "drafted" if attempt == 1 else f"redrafted ({attempt})",
                        draft.text, ms=self._ms(started), detail={"attempt": attempt})
            verdict = self.checker.check(draft.text, facts)
            if verdict.approved:
                self._trace(m.t, m.clock, m.id, "fact_checker", "approved",
                            f"{len(verdict.checked)} numbers and names match the match data",
                            detail={"checked": verdict.checked})
                approved = draft.text
                if attempt == 1:
                    self.stats["approved_first_time"] += 1
                break
            self.stats["caught"] += 1
            self._trace(m.t, m.clock, m.id, "fact_checker", "rejected", "; ".join(verdict.problems), status="rejected",
                        detail={"problems": verdict.problems, "checked": verdict.checked})
            feedback = verdict.problems

        fallback = approved is None
        if fallback:
            self.stats["fallbacks"] += 1
            approved = templates.fallback(m.kind, facts.values)
            self._trace(m.t, m.clock, m.id, "director", "fallback",
                        "Story failed fact-checking twice, so a plain stat card goes out instead", status="fallback")

        item, why = self.director.direct(m, facts, self.state.t, fallback)
        if item is None:
            self.stats["dropped"] += 1
            self._trace(m.t, m.clock, m.id, "director", "dropped", why, status="skipped")
            return None
        self._trace(m.t, m.clock, m.id, "director", "scheduled", why,
                    detail={"plugin": item["plugin"], "show_at": item["show_at"]})

        started = time.perf_counter()
        texts, notes = await self.persona.render(m, facts, approved)
        self._trace(m.t, m.clock, m.id, "persona", "rewrote",
                    f"{len(MODES)} viewer modes in {', '.join(self.languages)}"
                    + (f"; {len(notes)} kept the approved text" if notes else ""),
                    ms=self._ms(started), detail={"notes": notes})
        item["story"] = approved
        item["text"] = texts
        return self._emit(item)

    async def _handle_recap(self, m: Moment) -> dict | None:
        facts = self.recap.facts(m)
        texts: dict[str, dict[str, str]] = {}
        for lang in self.languages:
            text = await self.recap.write(m, facts, lang)
            verdict = self.checker.check(text, facts)
            if not verdict.approved:
                self._trace(m.t, m.clock, m.id, "fact_checker", "rejected", "; ".join(verdict.problems),
                            status="rejected")
                text = templates.fallback("recap", facts.values)
            texts[lang] = {mode: text for mode in MODES}
        self._trace(m.t, m.clock, m.id, "recap", "summarised",
                    f"{facts.values['home_short']} {facts.values['score_home']}-{facts.values['score_away']} "
                    f"{facts.values['away_short']}, top rated {facts.values['best_player']} "
                    f"({facts.values['best_rating']:.1f})")
        item, why = self.director.direct(m, facts, self.state.t, fallback=False)
        if item is None:
            return None
        self._trace(m.t, m.clock, m.id, "director", "scheduled", why, detail={"plugin": item["plugin"]})
        item["story"] = texts["en"]["analyst"]
        item["text"] = texts
        return self._emit(item)

    # --- helpers ------------------------------------------------------------------

    def _emit(self, item: dict) -> dict:
        self.overlays.append(item)
        self.publish("overlay", item)
        return item

    def _trace(self, t: float, clock: str, moment_id: str, agent: str, action: str, summary: str,
               status: str = "ok", ms: float = 0.0, detail: dict | None = None) -> None:
        self._step += 1
        step = TraceStep(f"st-{self._step:05d}", t, clock, moment_id, agent, action, summary, status, round(ms, 1),
                         detail or {}).to_dict()
        self.trace.append(step)
        self.publish("trace", step)

    @staticmethod
    def _ms(started: float) -> float:
        return (time.perf_counter() - started) * 1000
