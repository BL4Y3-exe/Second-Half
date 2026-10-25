"""The demo switch: a planted wrong number that the Fact-checker has to catch."""

import random

from agents import MockModel
from agents.fact_checker import FactChecker
from agents.slip import plant
from agents.types import Facts
from api.hub import MatchKey
from tests.test_agents import run_match


def test_a_planted_number_is_wrong_and_the_fact_checker_says_so():
    facts = Facts("m-1", {"player": "Ade Delacroix", "xg": 0.33, "distance_m": 9, "score_home": 2, "score_away": 1})
    text = "Ade Delacroix scores from 9 m, a 0.33 xG chance, and it's HAR 2-1 KMR."
    planted = plant(text, facts, random.Random(1))
    assert planted is not None
    new, said, says = planted
    assert said in ("9 m", "0.33 xG") and says != said and says in new and "2-1" in new
    verdict = FactChecker({"h-09": {"name": "Ade Delacroix"}}).check(new, facts)
    assert not verdict.approved and said.split()[0] in verdict.problems[0]
    assert plant("Ade Delacroix scores!", facts, random.Random(1)) is None


def test_with_the_switch_on_the_first_story_and_every_goal_get_a_planted_slip():
    orch, published = run_match(seed=9, model=MockModel(seed=9, mistake_rate=0.0), plant_slips=True)
    trace = [d for kind, d in published if kind == "trace"]
    planted = [s for s in trace if s["agent"] == "test"]
    goals = [d for kind, d in published if kind == "overlay" and d["kind"] == "goal"]
    assert goals and len(planted) == orch.stats["planted"] == len(goals) + 1
    for step in planted:
        after = [s for s in trace if s["moment_id"] == step["moment_id"] and s["id"] > step["id"]]
        assert after[0]["agent"] == "fact_checker" and after[0]["status"] == "rejected"
        assert step["detail"]["now"] in after[0]["summary"]
    assert orch.stats["caught"] == len(planted)  # a careful writer, so every catch is a planted one
    stories = {d["id"]: d["story"] for kind, d in published if kind == "overlay"}
    assert all(s["detail"]["now"] not in stories.get(s["moment_id"], "") for s in planted)


def test_the_switch_is_part_of_the_match():
    assert MatchKey("harbourside", "kingsmere", 9, 10.0, True).id == "harbourside-kingsmere-9-x10-planted"
    assert MatchKey("harbourside", "kingsmere", 9, 10.0) != MatchKey("harbourside", "kingsmere", 9, 10.0, True)
    _orch, published = run_match(seed=9, until=600)
    assert not any(d["agent"] == "test" for kind, d in published if kind == "trace")
