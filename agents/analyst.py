"""Analyst: pulls the context for a moment through the match tools.

The facts it returns are the only numbers and names a story may use.
"""

from __future__ import annotations

from mcp_server import MatchTools

from .types import Facts, Moment

OUTCOME_EN = {"saved": "saved", "blocked": "blocked", "off_target": "off target", "goal": "in"}
OUTCOME_ES = {"saved": "la para el portero", "blocked": "se la bloquean", "off_target": "se va fuera",
              "goal": "entra"}
SIDES = ("HOME", "AWAY")


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


class Analyst:
    name = "analyst"

    def __init__(self, tools: MatchTools):
        self.tools = tools

    def analyse(self, moment: Moment) -> Facts:
        calls: list[str] = []

        def call(name: str, *args):
            calls.append(f"{name}({', '.join(map(str, args))})")
            return getattr(self.tools, name)(*args)

        score = call("get_score")
        teams = score["teams"]
        f: dict = {
            "minute": int(moment.clock.split(":")[0]) + 1,
            "home": teams["HOME"]["name"], "away": teams["AWAY"]["name"],
            "home_short": teams["HOME"]["short"], "away_short": teams["AWAY"]["short"],
            "score_home": score["score"]["HOME"], "score_away": score["score"]["AWAY"],
            "label": moment.label,
        }
        sequence: list[dict] = []
        if moment.team in SIDES:
            side, opp = moment.team, "AWAY" if moment.team == "HOME" else "HOME"
            mine, theirs = call("get_team_stats", side), self.tools.get_team_stats(opp)
            f.update(team=mine["name"], team_short=teams[side]["short"], opp=theirs["name"],
                     opp_short=teams[opp]["short"], team_xg=round(mine["xg"], 2), opp_xg=round(theirs["xg"], 2),
                     team_shots=mine["shots"], opp_shots=theirs["shots"])
        if moment.player:
            p = call("get_player_stats", moment.player)
            f.update(player=p["name"], player_goals=p["goals"], player_shots=p["shots"], player_xg=round(p["xg"], 2),
                     distance_km=round(p["distance_m"] / 1000, 1), top_speed_kmh=round(p["top_speed_kmh"], 1),
                     goals_word=_plural(p["goals"], "goal", "goals"),
                     shots_word=_plural(p["shots"], "shot", "shots"),
                     goals_word_es=_plural(p["goals"], "gol", "goles"),
                     shots_word_es=_plural(p["shots"], "tiro", "tiros"))

        events = {e["id"]: e for e in self.tools.state.events[-200:]}
        source = [events[i] for i in moment.source_events if i in events]
        shot = next((e for e in source if e["type"] == "shot"), None)
        goal = next((e for e in source if e["type"] == "goal"), None)

        if moment.kind in ("goal", "big_chance", "shot_speed") and shot is not None:
            f.update(xg=round(shot["stats"]["xg"], 2), distance_m=round(shot["distance_m"]),
                     shot_speed_kmh=round(shot["shot_speed_kmh"]), outcome_text=OUTCOME_EN[shot["outcome"]],
                     outcome_text_es=OUTCOME_ES[shot["outcome"]], body_part=shot["body_part"])
            seq = call("get_sequence", shot["id"])
            sequence = seq["events"]
            if seq["passes"] >= 2:
                f["passes"] = seq["passes"]
                f["move_s"] = round(seq["duration_s"])
            assister = (goal or {}).get("assist") or shot.get("key_pass_by")
            if assister:
                f["assist"] = self.tools.get_player_stats(assister)["name"]
        elif moment.kind == "killer_pass" and source:
            ps = source[0]
            st = ps["stats"]
            passer = call("get_player_stats", ps["player"])
            f.update(passer=passer["name"], receiver=self.tools.get_player_stats(ps["receiver"])["name"],
                     difficulty=round(st["difficulty"], 2), difficulty_label=st["difficulty_label"],
                     lane_gap_m=round(st["lane_gap_m"], 1), distance_m=round(ps["distance_m"]),
                     progress_m=round(st["progress_m"]), passer_passes=passer["passes"],
                     passer_completion=round(passer["pass_completion_pct"] or 0))
            sequence = [ps]
        elif moment.kind == "momentum_swing" and moment.team in SIDES:
            st = self.tools.state
            now = st.t
            recent = [e for e in st.events if now - e["t"] <= 300 and e.get("team") == moment.team]
            call("get_trend", "momentum", 5)
            f.update(window_min=5, momentum=abs(round(st.momentum.score)),
                     tilt_recent=round(st.momentum.field_tilt()[moment.team]),
                     shots_recent=sum(1 for e in recent if e["type"] == "shot"),
                     final_third_recent=sum(1 for _t, s in st.momentum.final_third if s == moment.team))
        elif moment.kind in ("sprint_speed", "distance_10k"):
            if moment.kind == "sprint_speed":
                f["top_speed_kmh"] = round(float(moment.trigger["value"]), 1)
            else:
                f["milestone_km"] = 10
        return Facts(moment.id, f, sequence, calls)
