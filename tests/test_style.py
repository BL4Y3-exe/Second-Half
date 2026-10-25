"""House style: a graphic carries few numbers, and casual viewers get plain words."""

import asyncio

from agents import MockModel, style
from agents.fact_checker import FactChecker
from agents.persona import Persona
from agents.types import Facts, Moment
from tests.test_agents import run_match


def test_numbers_are_counted_the_way_a_viewer_reads_them():
    assert style.count_numbers("Hard 28 m pass through a 2.1 m lane, his 8th pass, 100% completion.") == 4
    assert style.count_numbers("GOAL! Holloway scores from 18 m. HAR 2-1 KMR.") == 1  # a score isn't a stat
    assert style.count_numbers("Una ocasión de 0,45 xG.") == 1
    assert style.count_numbers("Three shots and no goals.") == 0


def test_busy_lines_and_jargon_are_flagged_for_the_right_viewer():
    busy = "Hard 28 m pass through a 2.1 m gap, his 8th pass, and HAR have 0.75 xG."
    assert style.problems(busy) == ["has 4 numbers, too many for one graphic; keep the 3 that matter most"]
    assert style.problems("A 0.33 xG chance from 9 m.") == []
    assert style.problems("A 0.33 xG chance from 9 m.", "casual") == [
        "has 2 numbers, but a casual viewer gets one at most; keep the one that matters most",
        "uses xG, which a casual viewer won't know; say it in plain words"]
    assert style.problems("HAR ya manda en goles esperados.", "casual") == [
        "uses goles esperados, which a casual viewer won't know; say it in plain words"]
    assert style.problems("What a ball from Holloway, and HAR lead 1-0!", "casual") == []


def numbers_from(facts: dict, n: int) -> str:
    """Numbers that are all in the facts, so a line padded with them still passes fact-checking."""
    values = [v for k, v in facts.items() if isinstance(v, (int, float)) and not k.startswith("score")]
    return ", ".join(str(v) for v in values[:n])


class BusyModel(MockModel):
    """A Storyteller whose first draft is right but crammed with numbers; `redraft` is what it sends after."""

    def __init__(self, seed: int, redraft: str = "plain"):
        super().__init__(seed=seed, mistake_rate=0.0)
        self.redraft = redraft

    async def complete(self, agent, system, prompt, context):
        text = await super().complete(agent, system, prompt, context)
        if agent != "storyteller":
            return text
        if not context["feedback"]:
            return f"{text} Numbers: {numbers_from(context['facts'], 4)}."
        return text + (" It came from 999 m." if self.redraft == "wrong" else "")


def test_the_director_sends_a_busy_story_back_once():
    orch, published = run_match(seed=9, model=BusyModel(seed=9), until=900)
    trace = [d for kind, d in published if kind == "trace"]
    stories = [d for kind, d in published if kind == "overlay" and d["kind"] != "recap"]
    sent_back = [s for s in trace if s["action"] == "sent back"]
    assert stories and len(sent_back) == len(stories)
    assert all(s["agent"] == "director" and s["status"] == "retry" for s in sent_back)
    assert all("Numbers:" not in d["story"] and not d["fallback"] for d in stories)
    assert orch.stats["caught"] == 0  # a busy line isn't a wrong number


def test_a_busy_but_right_story_beats_a_wrong_redraft():
    orch, published = run_match(seed=9, model=BusyModel(seed=9, redraft="wrong"), until=900)
    trace = [d for kind, d in published if kind == "trace"]
    stories = [d for kind, d in published if kind == "overlay" and d["kind"] != "recap"]
    assert stories and all("Numbers:" in d["story"] and not d["fallback"] for d in stories)
    assert all("999" not in d["story"] for d in stories)
    assert sum(s["action"] == "kept" for s in trace) == len(stories) == orch.stats["caught"]


class JargonModel(MockModel):
    """A Persona that talks xG to casual viewers; `learns` says whether it drops it when told."""

    def __init__(self, learns: bool):
        super().__init__(seed=1)
        self.learns = learns

    async def complete(self, agent, system, prompt, context):
        if context.get("mode") != "casual":
            return await super().complete(agent, system, prompt, context)
        if self.learns and "Your last version" in prompt:
            return "Big chance for Delacroix, so close!"
        return "Big chance for Delacroix, the xG says so."


def render_casual(model: MockModel) -> tuple[dict, list[str], list[str]]:
    persona = Persona(model, FactChecker({"h-09": {"name": "Ade Delacroix"}}))
    moment = Moment("m-1", "big_chance", 600.0, "10:00", 2, "HOME", "h-09", "Big chance", {})
    facts = Facts("m-1", {"player": "Ade Delacroix", "xg": 0.33, "distance_m": 9, "outcome_text": "saved",
                          "outcome_text_es": "la para el portero", "player_shots": 2, "player_xg": 0.41,
                          "player_goals": 0, "shots_word": "shots", "goals_word": "goals", "shots_word_es": "tiros"})
    return asyncio.run(persona.render(moment, facts, "Ade Delacroix should score from 9 m, a 0.33 xG chance."))


def test_casual_jargon_gets_one_redraft_then_the_scripted_line():
    texts, notes, redrafts = render_casual(JargonModel(learns=True))
    assert texts["en"]["casual"] == "Big chance for Delacroix, so close!"
    assert notes == [] and redrafts == ["en/casual: uses xG, which a casual viewer won't know; say it in plain words",
                                        "es/casual: uses xG, which a casual viewer won't know; say it in plain words"]

    texts, notes, _redrafts = render_casual(JargonModel(learns=False))
    assert "xG" not in texts["en"]["casual"] and "xG" not in texts["es"]["casual"]
    assert len(notes) == 2 and all(n.endswith("used the scripted line") for n in notes)
