"""Run whole matches and save them as JSON."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .engine import SIDES, MatchEngine
from .tactics import PITCH_LENGTH, PITCH_WIDTH
from .teams import build_team

SCHEMA_VERSION = 1


def simulate_match(home: str = "harbourside", away: str = "kingsmere", seed: int = 42,
                   frame_step: float = 0.5) -> dict:
    """Simulate a full match and return it as a JSON-ready dict."""
    if home == away:
        raise ValueError("home and away must be different clubs")
    engine = MatchEngine(build_team(home, "HOME"), build_team(away, "AWAY"), seed=seed, frame_step=frame_step)
    result = engine.simulate()
    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "seed": seed,
            "pitch": [PITCH_LENGTH, PITCH_WIDTH],
            "tick_s": 0.1,
            "frame_step_s": frame_step,
            "first_kickoff": engine.first_kickoff,
            "home_attacks_right_in_first_half": True,
            "teams": {s: engine.teams[s].to_dict() for s in SIDES},
        },
        "summary": summarize(result["events"], engine),
        "lineups": result["lineups"],
        "events": result["events"],
        "frames": result["frames"],
    }


def summarize(events: list[dict], engine: MatchEngine) -> dict:
    """Simple box score straight from the events (the stats engine does the real analysis)."""
    per: dict[str, Counter] = {s: Counter() for s in SIDES}
    for ev in events:
        team = ev.get("team")
        if team not in per:
            continue
        c = per[team]
        typ = ev["type"]
        if typ == "pass":
            c["passes"] += 1
            if ev["outcome"] == "complete":
                c["passes_complete"] += 1
        elif typ == "shot":
            c["shots"] += 1
            if ev["outcome"] in ("goal", "saved"):
                c["shots_on_target"] += 1
        elif typ in ("tackle", "interception", "foul", "carry", "pressure", "goal"):
            c[typ + "s"] += 1
            if typ == "tackle" and ev["outcome"] == "won":
                c["tackles_won"] += 1
            if typ == "foul" and ev.get("card"):
                c["yellow_cards"] += 1
        elif typ == "out" and ev["restart"] == "corner":
            pass
    total_poss = sum(engine.possession_time.values()) or 1.0
    teams = {}
    for s in SIDES:
        c = per[s]
        teams[s] = {
            "name": engine.teams[s].name,
            "goals": engine.score[s],
            "possession_pct": round(100 * engine.possession_time[s] / total_poss, 1),
            "shots": c["shots"],
            "shots_on_target": c["shots_on_target"],
            "passes": c["passes"],
            "pass_completion_pct": round(100 * c["passes_complete"] / max(1, c["passes"]), 1),
            "carries": c["carrys"],
            "tackles": c["tackles"],
            "tackles_won": c["tackles_won"],
            "interceptions": c["interceptions"],
            "pressures": c["pressures"],
            "fouls": c["fouls"],
            "yellow_cards": c["yellow_cards"],
        }
    return {
        "score": dict(engine.score),
        "duration_s": round(engine.t, 1),
        "events": len(events),
        "teams": teams,
        "players": engine.player_physical(),
    }


def save_match(match: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(match, fh, separators=(",", ":"))
    return path
