import asyncio

import pytest

from agents import MockModel, Orchestrator
from agents.fact_checker import FactChecker
from agents.spotter import Spotter
from agents.types import Facts
from mcp_server import MatchTools, list_plugins
from simulator import MatchEngine, build_team
from stats import MatchState

PITCH_X = (-3.0, 108.0)
PITCH_Y = (-3.0, 71.0)


def run_match(seed: int, model=None, until: float | None = None,
              plant_slips: bool = False) -> tuple[Orchestrator, list[tuple[str, dict]]]:
    """Plays a match through the stats engine and the agent team, the way the live server does."""
    engine = MatchEngine(build_team("harbourside", "HOME"), build_team("kingsmere", "AWAY"), seed=seed, frame_step=0.5)
    state = MatchState({"teams": {s: t.to_dict() for s, t in engine.teams.items()}})
    published: list[tuple[str, dict]] = []
    orch = Orchestrator(state, lambda kind, data: published.append((kind, data)), speed=10, model=model, seed=seed,
                        plant_slips=plant_slips)

    async def play() -> None:
        for tick in engine.run():
            triggers = state.apply_frame(tick.frame) if tick.frame is not None else []
            for ev in tick.events:
                triggers += state.apply_event(ev)[1]
            orch.observe(tick.events, triggers, tick.t)
            await orch.drain()
            if until is not None and tick.t > until:
                break
        orch.flush(state.t)
        await orch.drain()

    asyncio.run(play())
    return orch, published


@pytest.fixture(scope="module")
def match():
    return run_match(seed=9, model=MockModel(seed=9, mistake_rate=0.3))


def test_fact_checker_catches_wrong_numbers_and_names():
    roster = {"h-09": {"name": "Ade Delacroix"}, "a-02": {"name": "Gus Renwick"}}
    checker = FactChecker(roster)
    facts = Facts("m-1", {"player": "Ade Delacroix", "xg": 0.33, "distance_m": 9, "shot_speed_kmh": 88})

    assert checker.check("Ade Delacroix shoots from 9 m at 88 km/h, a 0.33 xG chance.", facts).approved
    wrong_number = checker.check("Ade Delacroix shoots from 19 m, a 0.33 xG chance.", facts)
    assert not wrong_number.approved and wrong_number.problems
    assert not checker.check("Ade Delacroix shoots, a 0.45 xG chance.", facts).approved
    assert not checker.check("Gus Renwick shoots from 9 m.", facts).approved  # right numbers, wrong player


def test_every_goal_gets_a_card_and_both_halves_a_recap(match):
    orch, published = match
    overlays = [d for kind, d in published if kind == "overlay"]
    goals = [d for d in overlays if d["kind"] == "goal"]
    assert len(goals) == sum(orch.state.score.values())
    assert all(g["plugin"] == "goal-card" and g["priority"] == 1 for g in goals)
    recaps = [d for d in overlays if d["plugin"] == "recap-card"]
    assert [r["headline"] for r in recaps] == ["HALF TIME", "FULL TIME"]
    assert recaps[-1]["data"]["score_home"] == orch.state.score["HOME"]


def test_overlays_carry_checked_text_for_every_viewer(match):
    _orch, published = match
    plugins = {p["id"] for p in list_plugins()}
    for d in (d for kind, d in published if kind == "overlay"):
        assert d["plugin"] in plugins
        assert d["facts_checked"]
        for lang in ("en", "es"):
            for mode in ("analyst", "casual", "player"):
                assert d["text"][lang][mode].strip(), (d["id"], lang, mode)


def test_wrong_drafts_are_caught_and_rewritten(match):
    orch, published = match
    trace = [d for kind, d in published if kind == "trace"]
    rejected = [s for s in trace if s["agent"] == "fact_checker" and s["status"] == "rejected"]
    assert orch.stats["caught"] == len(rejected) > 0
    # each rejection is followed by a redraft of the same moment
    for step in rejected:
        later = [s for s in trace if s["moment_id"] == step["moment_id"] and s["id"] > step["id"]]
        assert later and later[0]["agent"] in ("storyteller", "director")


def test_director_spaces_out_minor_graphics(match):
    # Must-show items (goals, recaps) go straight on; the rest never overlap each other in a slot.
    _orch, published = match
    by_slot: dict[str, list[dict]] = {}
    for d in (d for kind, d in published if kind == "overlay" and d["priority"] > 1):
        by_slot.setdefault(d["slot"], []).append(d)
    for items in by_slot.values():
        items.sort(key=lambda d: d["show_at"])
        for prev, cur in zip(items, items[1:], strict=False):
            assert cur["show_at"] >= prev["show_at"] + prev["duration_s"] * 10 - 0.5


def test_telestrator_geometry_is_on_the_pitch(match):
    _orch, published = match
    drawings = [d["telestrator"] for kind, d in published if kind == "overlay" and d["telestrator"]]
    assert drawings
    for tele in drawings:
        assert tele["window"][0] < tele["window"][1]
        for arrow in tele["arrows"]:
            for x, y in (arrow["from"], arrow["to"]):
                assert PITCH_X[0] <= x <= PITCH_X[1] and PITCH_Y[0] <= y <= PITCH_Y[1]
            assert tele["window"][0] <= arrow["t"] <= tele["window"][1]


def test_a_goal_gets_a_goal_card_not_a_shot_card_as_well():
    def trigger(kind: str, t: float, priority: int, events: list[str]) -> dict:
        return {"id": f"tr-{kind}", "kind": kind, "t": t, "clock": "02:38", "priority": priority, "team": "AWAY",
                "player": "a-09", "label": kind, "source_events": events}

    spotter = Spotter()
    spotter.watch(trigger("shot_speed", 158.3, 2, ["e-86", "e-84"]))
    spotter.watch(trigger("goal", 158.9, 1, ["e-87", "e-86"]))  # the ball takes a moment to cross the line
    assert [(m, why) for m, _tr, why in spotter.release(159.9)] == [(None, "part of a goal moment")]
    assert [m.kind for m, _tr, _why in spotter.release(160.5)] == ["goal"]


class LyingModel(MockModel):
    """A Storyteller that always gets the distance wrong."""

    async def complete(self, agent, system, prompt, context):
        text = await super().complete(agent, system, prompt, context)
        return text + " It came from 999 m." if agent == "storyteller" else text


def test_story_that_keeps_failing_becomes_a_stat_card():
    orch, published = run_match(seed=9, model=LyingModel(seed=9, mistake_rate=0.0), until=900)
    overlays = [d for kind, d in published if kind == "overlay" and d["kind"] != "recap"]
    assert overlays and orch.stats["fallbacks"] == len(overlays)
    assert all(d["fallback"] and d["plugin"] == "stat-card" for d in overlays)
    assert all(d["fallback_reason"] == "fact_check" for d in overlays)
    assert all("999" not in d["story"] for d in overlays)


def test_match_tools(match):
    orch, _ = match
    tools = MatchTools(orch.state)
    score = tools.get_score()
    assert score["score"] == orch.state.score and score["finished"]
    goal = next(e for e in orch.state.events if e["type"] == "goal")
    by_name = tools.get_player_stats(orch.state.players[goal["player"]]["name"])
    assert by_name["goals"] >= 1
    seq = tools.get_sequence(goal["id"])
    assert seq["events"] and seq["events"][-1]["type"] in ("shot", "goal")
    manifests = tools.list_plugins()
    assert {"goal-card", "recap-card", "stat-card"} <= {m["id"] for m in manifests}
    for m in manifests:
        assert {"id", "name", "slot", "needs", "default_duration_s"} <= m.keys()


def test_momentum_swings_use_the_sandboxed_outside_plugin(match):
    _orch, published = match
    swings = [d for kind, d in published if kind == "overlay" and d["kind"] == "momentum_swing" and not d["fallback"]]
    assert swings
    for d in swings:
        assert d["plugin"] == "xg-race"
        assert d["plugin_info"]["entry"] == "/plugins/xg-race/index.html"
        race = d["data"]["xg_race"]
        assert set(race["teams"]) == {"HOME", "AWAY"} and race["now"] > 0


def test_director_falls_back_to_builtin_without_match_tools():
    from agents.director import Director
    from agents.types import Facts, Moment

    moment = Moment("m-1", "momentum_swing", 600.0, "10:00", 2, "HOME", None, "Momentum", {})
    item, _why = Director(speed=10).direct(moment, Facts("m-1", {"team_short": "HAR"}), now=600.0, fallback=False)
    assert item["plugin"] == "momentum-bar" and "plugin_info" not in item
