import json

import pytest

from simulator import CLUBS, MatchEngine, build_team, simulate_match
from simulator import physics as ph
from simulator.export import save_match

PITCH_MARGIN = 2.0


@pytest.fixture(scope="module")
def match():
    return simulate_match("harbourside", "kingsmere", seed=7, frame_step=1.0)


def test_same_seed_same_match():
    a = simulate_match(seed=3, frame_step=5.0)
    b = simulate_match(seed=3, frame_step=5.0)
    assert a["events"] == b["events"]
    assert a["frames"] == b["frames"]


def test_different_seeds_differ():
    a = simulate_match(seed=1, frame_step=60.0)
    b = simulate_match(seed=2, frame_step=60.0)
    assert a["events"] != b["events"]


def test_rosters_are_stable_and_unique():
    for key in CLUBS:
        home = build_team(key, "HOME")
        assert home == build_team(key, "HOME")
        assert len(home.players) == 16
        assert home.starters[0].position == "GK"
        assert len({p.id for p in home.players}) == 16
        assert len({p.name for p in home.players}) == 16
        assert all(p.id.startswith("h-") for p in home.players)
        assert all(p.id.startswith("a-") for p in build_team(key, "AWAY").players)


def test_match_runs_full_time(match):
    types = [e["type"] for e in match["events"]]
    assert types[0] == "kickoff"
    assert types[-1] == "full_time"
    assert types.count("half_time") == 1
    assert match["summary"]["duration_s"] > 90 * 60


def test_events_are_ordered_and_well_formed(match):
    ids = set()
    last_t = -1.0
    for ev in match["events"]:
        assert ev["id"] not in ids
        ids.add(ev["id"])
        assert ev["t"] >= last_t
        last_t = ev["t"]
        assert ev["period"] in (1, 2)
        assert {"id", "t", "period", "clock", "type"} <= ev.keys()
    json.dumps(match)  # everything must be JSON-serialisable


def test_score_matches_goal_events(match):
    goals = [e for e in match["events"] if e["type"] == "goal"]
    score = match["summary"]["score"]
    assert len(goals) == score["HOME"] + score["AWAY"]
    for side in ("HOME", "AWAY"):
        assert sum(1 for g in goals if g["team"] == side) == score[side]
    shots = {e["player"] for e in match["events"] if e["type"] == "shot" and e["outcome"] == "goal"}
    assert {g["player"] for g in goals} == shots


def test_positions_stay_on_pitch(match):
    for f in match["frames"]:
        assert len(f["p"]) == 22
        for x, y in f["p"] + [f["b"]]:
            assert -PITCH_MARGIN <= x <= 105 + PITCH_MARGIN
            assert -PITCH_MARGIN <= y <= 68 + PITCH_MARGIN


def test_substitutions_update_lineups(match):
    subs = [e for e in match["events"] if e["type"] == "substitution"]
    assert len(match["lineups"]) == 1 + len(subs)
    assert len(subs) <= 6
    for sub, lineup in zip(subs, match["lineups"][1:], strict=True):
        ids = lineup[sub["team"]]
        assert ids[sub["slot"]] == sub["player_in"]
        assert sub["player_out"] not in ids


def test_stats_are_plausible():
    """Averaged over a few seeds the match should look like football, not noise."""
    goals = shots = passes = complete = 0
    distances = []
    seeds = [11, 12, 13]
    for seed in seeds:
        m = simulate_match(seed=seed, frame_step=60.0)
        ev = m["events"]
        goals += sum(1 for e in ev if e["type"] == "goal")
        shots += sum(1 for e in ev if e["type"] == "shot")
        p = [e for e in ev if e["type"] == "pass"]
        passes += len(p)
        complete += sum(1 for e in p if e["outcome"] == "complete")
        distances += [v["distance_m"] for v in m["summary"]["players"].values() if v["distance_m"] > 8000]
    n = len(seeds)
    assert 0.5 <= goals / n <= 6
    assert 8 <= shots / n <= 45
    assert 700 <= passes / n <= 2200
    assert 0.65 <= complete / passes <= 0.9
    assert 8000 <= sorted(distances)[len(distances) // 2] <= 14000


def test_live_stream_yields_ticks_every_tenth_of_a_second():
    engine = MatchEngine(build_team("ashford", "HOME"), build_team("northgate", "AWAY"), seed=5)
    ticks = []
    for tick in engine.run():
        ticks.append(tick)
        if len(ticks) == 50:
            break
    assert [round(t.t, 1) for t in ticks[:3]] == [0.0, 0.1, 0.2]
    assert all(t.frame is not None for t in ticks)
    assert ticks[0].events[0]["type"] == "kickoff"


def test_save_match_roundtrip(tmp_path, match):
    path = save_match(match, tmp_path / "m.json")
    assert json.loads(path.read_text(encoding="utf-8"))["summary"] == match["summary"]


def test_geometry_helpers():
    assert ph.dist((0, 0), (3, 4)) == 5
    d, f = ph.point_segment((5, 1), (0, 0), (10, 0))
    assert d == pytest.approx(1) and f == pytest.approx(0.5)
    close = ph.shot_quality(8, ph.goal_angle((97, 34)), 0, False)
    far = ph.shot_quality(28, ph.goal_angle((77, 34)), 0, False)
    assert close > far
    assert ph.position_value((100, 34)) > ph.position_value((50, 34))
