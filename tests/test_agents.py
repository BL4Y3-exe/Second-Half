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


def test_the_half_time_recap_shows_both_shapes(match):
    _orch, published = match
    half, full = [d for kind, d in published if kind == "overlay" and d["plugin"] == "recap-card"]
    for side in ("HOME", "AWAY"):
        for state in ("on", "off"):
            shape = half["data"]["shapes"][side][state]
            assert len(shape["positions"]) == 11 and shape["formation"].count("-") >= 2
    assert "shapes" not in full["data"]


def test_fact_checker_reads_a_formation_whole():
    checker = FactChecker({})
    facts = Facts("m-1", {"away_shape_on": "4-2-3-1", "away_shape_off": "4-2-4", "away_line_on_m": 28,
                          "away_line_off_m": 22, "score_home": 2, "score_away": 0})
    assert checker.check("Without the ball they went from 4-2-3-1 to 4-2-4 and dropped from 28 m to 22 m. 2-0.",
                         facts).approved
    wrong = checker.check("Without the ball they switched to a 4-3-3.", facts)
    assert not wrong.approved and "4-3-3" in wrong.problems[0]
    assert not checker.check("It is 3-0.", facts).approved  # a score is still two numbers


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


def test_counter_press_waits_for_its_move_and_folds_into_a_bigger_chance():
    def trigger(kind: str, t: float, priority: int, events: list[str]) -> dict:
        return {"id": f"tr-{kind}-{t}", "kind": kind, "t": t, "clock": "69:21", "priority": priority,
                "team": "AWAY", "player": "a-09", "label": kind, "source_events": events}

    spotter = Spotter()
    spotter.watch(trigger("counter_press", 4161.0, 2, ["e-40", "e-44"]))
    spotter.watch(trigger("shot_speed", 4161.0, 2, ["e-44"]))  # same shot: decided with the counter-press
    assert spotter.release(4163.0) == []
    spotter.watch(trigger("big_chance", 4165.6, 1, ["e-47"]))  # the rebound
    released = [(m.kind if m else None, why) for m, _tr, why in spotter.release(4169.5)]
    assert released == [(None, "part of a bigger chance"), ("shot_speed", "flagged"), ("big_chance", "flagged")]
    # On its own, a counter-press goes on air once its move is over.
    spotter.watch(trigger("counter_press", 4400.0, 2, ["e-90", "e-93"]))
    assert spotter.release(4405.0) == []
    assert [m.kind for m, _tr, _why in spotter.release(4408.5)] == ["counter_press"]


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


def test_every_moment_kind_has_stories_and_a_card():
    from agents import templates
    from agents.director import PLUGIN_FOR
    from stats.state import PRIORITY

    plugins = {p["id"] for p in list_plugins()}
    for kind in PRIORITY:
        assert templates.STORY[kind] and kind in templates.FALLBACK and kind in templates.FALLBACK_ES
        assert PLUGIN_FOR[kind] in plugins
        for lang, modes in templates.PERSONA.items():
            for mode, kinds in modes.items():
                assert kind in kinds, f"no {lang} {mode} line for {kind}"


def test_counter_press_moment_goes_on_air_checked():
    _orch, published = run_match(seed=6, model=MockModel(seed=6, mistake_rate=0.0), until=900)
    cards = [d for kind, d in published if kind == "overlay" and d["kind"] == "counter_press"]
    assert cards, "seed 6 has a ball won back and shot at within the Rangnick window"
    card = cards[0]
    assert card["plugin"] == "press-card" and not card["fallback"]
    assert card["data"]["won_back_s"] <= 8 and card["data"]["counter_press_wins"] >= 1
    assert any(z["label"] == "won back" for z in card["telestrator"]["zones"])


def test_a_goal_that_came_through_a_half_space_says_so():
    # Seed 1, 38:14: the move into the box goes through Kingsmere's right half-space.
    _orch, published = run_match(seed=1, model=MockModel(seed=1, mistake_rate=0.0), until=2400)
    goal = next(d for kind, d in published if kind == "overlay" and d["kind"] == "goal" and d["clock"] == "38:14")
    assert goal["data"]["half_space"] == "right"


def test_counter_press_that_makes_a_big_chance_goes_on_the_chance_card():
    # Seed 1, 69:21: Kingsmere win it back, shoot, win it back again and have a 0.93 xG chance saved.
    _orch, published = run_match(seed=1, model=MockModel(seed=1, mistake_rate=0.0), until=4400)
    overlays = [d for kind, d in published if kind == "overlay"]
    assert not [d for d in overlays if d["kind"] == "counter_press" and d["clock"].startswith("69:")]
    chance = next(d for d in overlays if d["kind"] == "big_chance" and d["clock"].startswith("69:"))
    assert chance["data"]["won_back_s"] <= 8
    assert any(z["label"] == "won back" for z in chance["telestrator"]["zones"])
