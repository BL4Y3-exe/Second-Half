import pytest

from simulator import simulate_match
from stats import analyse_match, xg
from stats.control_chaos import ControlChaos
from stats.counter_press import WINDOW_S, CounterPress
from stats.lanes import LANES, lane
from stats.momentum import PPDA_MIN_ACTIONS, Momentum
from stats.passes import difficulty, lane_gap
from stats.shape import formation
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
    for seed in range(40, 52):
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


def test_ppda_waits_for_a_few_defensive_actions():
    m = Momentum()
    # Away, attacking towards x = 0 in the first half, passes in its own 60% (x > 42): ten passes Home allows.
    for n in range(10):
        m.update({"t": n, "type": "pass", "team": "AWAY", "period": 1, "from": [80.0, 30.0], "to": [70.0, 30.0],
                  "outcome": "complete"})
    for n in range(PPDA_MIN_ACTIONS):
        assert m.ppda()["HOME"] is None
        m.update({"t": 20 + n, "type": "tackle", "team": "HOME", "period": 1, "at": [75.0, 34.0], "outcome": "won"})
    assert m.ppda() == {"HOME": round(10 / PPDA_MIN_ACTIONS, 1), "AWAY": None}


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


def _change(n: int, t: float, team: str, reason: str, x: float) -> dict:
    return {"id": f"e-{n}", "t": t, "period": 1, "type": "possession_change", "team": team, "reason": reason,
            "at": [x, 34.0]}


def test_counter_press_won_and_escaped():
    cp = CounterPress()
    cp.event(_change(1, 0.0, "HOME", "kickoff", 52.5), "00:00")
    # Home (attacking towards x = 105 in the first half) loses it at x = 80 and wins it back 3.2 s later.
    assert cp.event(_change(2, 10.0, "AWAY", "interception", 80.0), "00:10") is None
    won = cp.event(_change(3, 13.2, "HOME", "tackle", 78.0), "00:13")
    assert won is not None and won["outcome"] == "won" and won["seconds"] == 3.2 and won["team"] == "HOME"
    # Now Away has lost it, but in its own half (x = 78 is deep for a team attacking towards x = 0): no window.
    assert cp.window is None
    # Home loses it high again; three home players close the ball down, but Away gets away.
    cp.event(_change(4, 20.0, "AWAY", "loose_ball", 85.0), "00:20")
    near = {"h-02": (84.0, 34.0), "h-03": (86.0, 33.0), "h-04": (85.0, 37.0), "h-05": (60.0, 20.0)}
    assert cp.frame(21.0, (85.0, 34.0), near, "00:21") is None
    escaped = cp.frame(20.0 + WINDOW_S + 0.1, (70.0, 34.0), near, "00:28")
    assert escaped is not None and escaped["outcome"] == "escaped" and escaped["pressers"] == 3
    # A loss nobody chases is not a counter-press at all.
    cp.event(_change(5, 40.0, "HOME", "interception", 30.0), "00:40")
    cp.event(_change(6, 50.0, "AWAY", "interception", 90.0), "00:50")
    assert cp.frame(50.0 + WINDOW_S + 0.1, (90.0, 34.0), {"h-02": (70.0, 30.0)}, "00:58") is None
    # Away loses it high and wins it straight back off the man who took it: a bounce, not a counter-press.
    cp.event(_change(7, 60.0, "HOME", "interception", 30.0), "01:00")
    assert cp.event(_change(8, 60.4, "AWAY", "tackle", 31.0), "01:00") is None
    assert cp.stats("AWAY")["counter_presses"] == 0
    assert cp.stats("HOME") == {"counter_presses": 2, "counter_press_wins": 1, "counter_press_win_pct": 50.0}


def test_lanes_are_named_from_the_attacking_side():
    # Attacking towards x = 105 the top touchline (y = 0) is on a team's left; attacking the other way, on its right.
    assert lane(5, 1) == "left_wing" and lane(5, -1) == "right_wing"
    assert lane(20, 1) == "left_half_space" and lane(20, -1) == "right_half_space"
    assert lane(34, 1) == lane(34, -1) == "centre"
    assert lane(50, 1) == "right_half_space" and lane(63, 1) == "right_wing"


def test_final_third_entries_by_lane(state):
    for side in SIDES:
        entries = state.team_stats(side)["final_third_entries"]
        assert list(entries) == list(LANES)
        counted = [e for e in state.events if e.get("team") == side and e.get("stats", {}).get("final_third_entry")]
        assert sum(entries.values()) == len(counted) > 0
    for e in state.events:
        st = e.get("stats", {})
        if "lane" in st:  # only balls that end up in the final third get a lane
            assert e["type"] == "carry" or (e["type"] == "pass" and e["outcome"] == "complete")
            assert st["lane"] in LANES


def test_counter_press_in_a_match(state):
    for side in SIDES:
        st = state.team_stats(side)
        assert 0 <= st["counter_press_wins"] <= st["counter_presses"]
    records = state.counter_press.records
    assert records and {r["outcome"] for r in records} <= {"won", "escaped"}
    assert all(r["seconds"] <= WINDOW_S for r in records if r["outcome"] == "won")
    won_events = {e["id"]: e for e in state.events if "won_back_s" in e.get("stats", {})}
    assert {r["event"] for r in records if r["outcome"] == "won"} == set(won_events)
    for tr in (t for t in state.triggers if t["kind"] == "counter_press"):
        assert tr["value"] <= WINDOW_S and len(tr["source_events"]) >= 2


def test_formation_reads_lines_from_the_back():
    assert formation([20, 21, 20, 22, 38, 40, 39, 41, 55, 56]) == "4-4-2"
    assert formation([20, 21, 20, 22, 30, 40, 41, 52, 53, 54]) == "4-1-2-3"
    assert formation([54, 20, 40, 21, 30, 53, 22, 41, 20, 52]) == "4-1-2-3"  # in any order


def test_average_shapes_in_a_match(state):
    for side in SIDES:
        for period in (1, 2):
            for with_ball in (True, False):
                shape = state.shape.shape(period, side, with_ball)
                assert len(shape["positions"]) == 11
                assert all(0 <= x <= 105 and 0 <= y <= 68 for x, y in shape["positions"])
                assert shape["positions"][0][0] < 20  # the goalkeeper, in the team's own end both halves
                assert sum(map(int, shape["formation"].split("-"))) == 10
                assert 0 < shape["back_line_m"] < 60 and shape["length_m"] > 0
    assert state.shape.shape(3, "HOME", True) is None
