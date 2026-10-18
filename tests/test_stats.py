import pytest

from simulator import simulate_match
from stats import analyse_match, xg
from stats.control_chaos import ControlChaos
from stats.passes import difficulty, lane_gap
from stats.speed import SpeedTracker
from stats.state import PRIORITY, SIDES


@pytest.fixture(scope="module")
def state():
    return analyse_match(simulate_match("harbourside", "kingsmere", seed=5, frame_step=0.5))


def test_xg_reference_values():
    assert xg(6, 62.8) == pytest.approx(0.56, abs=0.03)
    assert xg(11, 36.9) == pytest.approx(0.28, abs=0.03)
    assert xg(18, 22.9) == pytest.approx(0.10, abs=0.02)
    assert xg(11, 36.9, body_part="head") < xg(11, 36.9)
    assert xg(11, 36.9, pressure=1.0) < xg(11, 36.9)


def test_xg_tracks_goals_over_many_matches():
    goals = expected = 0.0
    for seed in range(40, 46):
        st = analyse_match(simulate_match(seed=seed, frame_step=30.0))
        for side in SIDES:
            goals += st.score[side]
            expected += st.team_stats(side)["xg"]
    assert 0.6 <= goals / expected <= 1.5


def test_pass_difficulty_bounds():
    assert difficulty(5, 0, 20, 20) < 0.15
    assert difficulty(45, 1, 0, 0) == 1.0
    assert lane_gap((0, 0), (20, 0), [(10, 3), (1, 0)]) == pytest.approx(3)  # (1, 0) is pressure, not the lane


def test_speed_tracker():
    tr = SpeedTracker()
    tr.update(0.0, {"p": (0.0, 0.0)})
    tr.update(1.0, {"p": (9.0, 0.0)})  # 32.4 km/h
    tr.update(2.0, {"p": (18.0, 0.0)})
    r = tr.runners["p"]
    assert r.distance_m == pytest.approx(18)
    assert r.top_speed_kmh == pytest.approx(32.4)
    assert r.sprints == 1
    tr.update(3.0, {"p": (80.0, 0.0)})  # a jump, not running
    assert r.distance_m == pytest.approx(18)


def test_control_chaos_range():
    cc = ControlChaos()
    calm = [{"t": i * 3.0, "type": "pass", "outcome": "complete"} for i in range(60)]
    for ev in calm:
        cc.update(ev)
    settled = cc.index()
    for i in range(30):
        cc.update({"t": 180 + i, "type": "possession_change"})
        cc.update({"t": 180 + i + 0.5, "type": "tackle"})
    assert 0 <= cc.index() < settled <= 100


def test_state_totals_match_events(state):
    events = state.events
    for side in SIDES:
        ts = state.team_stats(side)
        assert ts["goals"] == sum(1 for e in events if e["type"] == "goal" and e["team"] == side)
        assert ts["passes"] == sum(1 for e in events if e["type"] == "pass" and e["team"] == side)
        shots = [e for e in events if e["type"] == "shot" and e["team"] == side]
        assert ts["xg"] == pytest.approx(sum(e["stats"]["xg"] for e in shots), abs=0.02)
        assert 0 < ts["distance_km"] < 160
    pct = state.possession_pct()
    assert pct["HOME"] + pct["AWAY"] == pytest.approx(100, abs=0.2)
    assert state.finished


def test_events_are_enriched(state):
    passes = [e for e in state.events if e["type"] == "pass"]
    assert all(0 <= e["stats"]["difficulty"] <= 1 for e in passes)
    shots = [e for e in state.events if e["type"] == "shot"]
    assert all(0 < e["stats"]["xg"] < 1 for e in shots)


def test_player_stats_and_speeds(state):
    players = [state.player_stats(p) for p in state.players]
    played = [p for p in players if p["distance_m"] > 0]
    assert len(played) >= 22
    assert max(p["top_speed_kmh"] for p in played) < 38
    assert sum(p["goals"] for p in players) == sum(state.score.values())


def test_triggers(state):
    assert state.triggers, "a full match should produce some key-moment triggers"
    kinds = {t["kind"] for t in state.triggers}
    assert kinds <= set(PRIORITY)
    goals = sum(state.score.values())
    assert sum(1 for t in state.triggers if t["kind"] == "goal") == goals
    assert sum(1 for t in state.triggers if t["kind"] == "distance_10k") <= 3
    for t in state.triggers:
        assert t["priority"] in (1, 2, 3)
        assert t["label"]


def test_snapshot_and_trend(state):
    snap = state.snapshot()
    assert snap["score"] == state.score
    assert set(snap["teams"]) == set(SIDES)
    trend = state.trend("xg", window_minutes=10)
    assert 1 <= len(trend) <= 12
    assert all("minute" in p and "value" in p for p in trend)
