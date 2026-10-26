"""Recap: half-time and full-time summaries with player ratings."""

from __future__ import annotations

import json
import random
from pathlib import Path

from mcp_server import MatchTools

from . import templates
from .models import ModelClient
from .types import Facts, Moment

SHAPE_MOVE_M = 4  # a back line that moves less than this without the ball is not worth a sentence

SYSTEM = (Path(__file__).parent / "prompts" / "recap.md").read_text(encoding="utf-8")


def rating(p: dict, conceded: int) -> float:
    """A simple 0-10 match rating from the stats engine's numbers."""
    r = 6.0
    r += 1.0 * p["goals"] + 0.6 * p["assists"] + 0.4 * p["xg"] + 0.3 * p.get("xa", 0.0)
    r += 0.15 * p["key_passes"] + 0.12 * p["tackles_won"] + 0.1 * p["interceptions"] + 0.3 * p["saves"]
    r += 0.06 * p["blocks"] + 0.04 * p["clearances"]
    if p["passes"] >= 15 and p["pass_completion_pct"] is not None:
        r += (p["pass_completion_pct"] - 75) / 40
    if p["position"] in ("GK", "CB", "LB", "RB"):
        r -= 0.25 * conceded
    r -= 0.3 * p["yellow_cards"]
    return round(max(3.0, min(9.9, r)), 1)


def add_shapes(f: dict, st) -> None:
    """Each team's average shape in the first half, with the ball and without it, plus one sentence on the team
    whose shape changed most when it lost the ball: a different formation first, then the back line moving most."""
    shapes = {}
    for side, key in (("HOME", "home"), ("AWAY", "away")):
        on, off = st.shape.shape(1, side, True), st.shape.shape(1, side, False)
        if on is None or off is None:
            return
        shapes[side] = {"on": on, "off": off}
        f[f"{key}_shape_on"], f[f"{key}_shape_off"] = on["formation"], off["formation"]
        f[f"{key}_line_on_m"], f[f"{key}_line_off_m"] = on["back_line_m"], off["back_line_m"]
    f["shapes"] = shapes

    def change(key: str) -> tuple[bool, int]:
        return f[f"{key}_shape_on"] != f[f"{key}_shape_off"], abs(f[f"{key}_line_on_m"] - f[f"{key}_line_off_m"])

    key = max(("home", "away"), key=change)
    switched, moved = change(key)
    if not switched and moved < SHAPE_MOVE_M:
        return
    team, on, off = f[key], f[f"{key}_shape_on"], f[f"{key}_shape_off"]
    line_on, line_off = f[f"{key}_line_on_m"], f[f"{key}_line_off_m"]
    deeper = line_off < line_on
    en = f"went from {on} to {off}" if switched else f"kept their {on}"
    es = f"pasó del {on} al {off}" if switched else f"mantuvo su {on}"
    if moved >= SHAPE_MOVE_M:
        en += f" and {'dropped' if deeper else 'pushed up'} their back line from {line_on} m to {line_off} m"
        es += f" y {'retrasó' if deeper else 'adelantó'} su línea defensiva de {line_on} m a {line_off} m"
    f["shape_line"] = f" Without the ball, {team} {en}."
    f["shape_line_es"] = f" Sin balón, {team} {es}."


class Recap:
    name = "recap"

    def __init__(self, model: ModelClient, tools: MatchTools):
        self.model = model
        self.tools = tools

    def facts(self, moment: Moment) -> Facts:
        st = self.tools.state
        h, a = st.team_stats("HOME"), st.team_stats("AWAY")
        ratings = []
        for pid, info in st.players.items():
            p = st.player_stats(pid)
            if p["distance_m"] < 500:  # did not really play
                continue
            conceded = st.score["AWAY" if info["side"] == "HOME" else "HOME"]
            ratings.append({"id": pid, "name": p["name"], "team": info["side"], "rating": rating(p, conceded)})
        ratings.sort(key=lambda r: r["rating"], reverse=True)
        goals = [e for e in st.events if e["type"] == "goal"]
        names = {pid: info["name"] for pid, info in st.players.items()}
        f: dict = {
            "label": moment.label, "label_es": "Descanso" if moment.label == "Half time" else "Final",
            "home": st.teams["HOME"]["name"], "away": st.teams["AWAY"]["name"],
            "home_short": st.teams["HOME"]["short"], "away_short": st.teams["AWAY"]["short"],
            "score_home": st.score["HOME"], "score_away": st.score["AWAY"],
            "home_xg": h["xg"], "away_xg": a["xg"], "home_shots": h["shots"], "away_shots": a["shots"],
            "home_poss": round(h["possession_pct"]), "away_poss": round(a["possession_pct"]),
            "best_player": ratings[0]["name"], "best_rating": ratings[0]["rating"],
            "ratings": ratings[:6],
            "goals": [{"minute": int(g["clock"].split(":")[0]) + 1, "player": names[g["player"]], "team": g["team"]}
                      for g in goals],
        }
        for i, g in enumerate(f["goals"], 1):
            f[f"goal_minute_{i}"] = g["minute"]
            f[f"goal_scorer_{i}"] = g["player"]
        lines = ", ".join(f"{g['player'].split()[-1]} {g['minute']}'" for g in f["goals"])
        f["goals_line"] = f" Goals: {lines}." if lines else ""
        f["goals_line_es"] = f" Goles: {lines}." if lines else ""
        for r in ratings[:6]:
            f[f"rating_{r['id']}"] = r["rating"]
        f["shape_line"] = f["shape_line_es"] = ""
        if moment.label == "Half time":
            add_shapes(f, st)
        return Facts(moment.id, f, [], ["get_score()", "get_team_stats(HOME)", "get_team_stats(AWAY)",
                                         "get_player_stats(*)"])

    async def write(self, moment: Moment, facts: Facts, lang: str) -> str:
        prompt = f"{moment.label}. Language: {lang}.\nFacts: {json.dumps(facts.for_model(), ensure_ascii=False)}"
        context = {"facts": facts.values, "kind": "recap", "clock": moment.clock, "lang": lang}
        return (await self.model.complete("recap", SYSTEM, prompt, context)).strip()

    def scripted(self, moment: Moment, facts: Facts, lang: str) -> str:
        """The recap built from the facts alone, for when the model can't be used."""
        return templates.recap({"facts": facts.values, "lang": lang}, random.Random(moment.clock))
