"""The single match state everything downstream reads (agents, MCP server, API).

Feed it simulator events and position frames in time order. It enriches
events with computed numbers (xG, pass difficulty, ...), keeps running team
and player stats, and fires threshold triggers such as a 32 km/h sprint or a
100 km/h shot that the Spotter agent turns into key moments.
"""

from __future__ import annotations

import math
from collections import defaultdict

from .control_chaos import ControlChaos
from .momentum import Momentum, other
from .passes import difficulty, difficulty_label, lane_gap, receiver_space
from .speed import SpeedTracker
from .xg import shot_xg

SIDES = ("HOME", "AWAY")

SPRINT_TRIGGER_KMH = 32.0
SHOT_TRIGGER_KMH = 100.0
DISTANCE_TRIGGER_M = 10_000
BIG_CHANCE_XG = 0.3
KILLER_PASS_DIFFICULTY = 0.6
DISTANCE_TRIGGER_LIMIT = 3  # only the first few players past 10 km are news

# 1 = must show, 2 = worth showing, 3 = filler. The Spotter agent starts from this.
PRIORITY = {"goal": 1, "big_chance": 1, "momentum_swing": 2, "shot_speed": 2, "killer_pass": 2,
            "sprint_speed": 2, "distance_10k": 3}

PLAYER_COUNTERS = (
    "passes", "passes_complete", "key_passes", "shots", "shots_on_target", "goals", "assists", "tackles",
    "tackles_won", "interceptions", "fouls", "pressures", "carries", "clearances", "saves", "blocks",
)
TEAM_COUNTERS = PLAYER_COUNTERS + ("corners", "throw_ins", "offsides", "yellow_cards", "final_third_passes")


def _r(v: float, n: int = 2) -> float:
    return round(v, n)


class MatchState:
    def __init__(self, meta: dict, lineup: dict | None = None):
        self.meta = meta
        self.teams = meta["teams"]
        self.players: dict[str, dict] = {}
        for side in SIDES:
            for p in self.teams[side]["players"]:
                self.players[p["id"]] = {**p, "side": side}
        if lineup is None:
            lineup = {s: [p["id"] for p in self.teams[s]["players"][:11]] for s in SIDES}
        self.slots = {s: list(lineup[s]) for s in SIDES}

        self.t = 0.0
        self.period = 1
        self.clock = "00:00"
        self.score = {s: 0 for s in SIDES}
        self.finished = False

        self.team = {s: defaultdict(float) for s in SIDES}
        self.player = {pid: defaultdict(float) for pid in self.players}
        self.speed = SpeedTracker()
        self.control = ControlChaos()
        self.momentum = Momentum()

        self.possession: str | None = None
        self._poss_since = 0.0
        self.possession_time = {s: 0.0 for s in SIDES}

        self.last_frame: dict | None = None
        self.events: list[dict] = []
        self.triggers: list[dict] = []
        self.history: list[dict] = []
        self._fired: set[tuple[str, str]] = set()
        self._period_seen = 1
        self._period_start = 0.0
        self._speed_record = SPRINT_TRIGGER_KMH
        self._distance_fired = 0
        self._trigger_n = 0
        self._last_pass: dict | None = None

    # ------------------------------------------------------------------
    # input

    def positions(self) -> dict[str, tuple[float, float]]:
        """Current player positions by id, from the latest frame."""
        if self.last_frame is None:
            return {}
        ids = self.slots["HOME"] + self.slots["AWAY"]
        return {pid: tuple(xy) for pid, xy in zip(ids, self.last_frame["p"], strict=True)}

    def apply_frame(self, frame: dict) -> list[dict]:
        self.last_frame = frame
        self._advance(frame["t"], frame["period"])
        out = []
        for pid, kind, value in self.speed.update(frame["t"], self.positions(), frame["period"]):
            # Only a new fastest-of-the-match sprint above the threshold is news.
            if kind == "top_speed" and value > self._speed_record + 0.2:
                self._speed_record = value
                if self.t < 300:  # early sprints set the bar; they are not news yet
                    continue
                out.append(self._trigger("sprint_speed", self.players[pid]["side"], pid, round(value, 1),
                                         f"{self._name(pid)} hits {value:.1f} km/h, fastest of the match"))
        if self._distance_fired < DISTANCE_TRIGGER_LIMIT:
            for pid, runner in self.speed.runners.items():
                if runner.distance_m >= DISTANCE_TRIGGER_M and (pid, "distance") not in self._fired:
                    self._fired.add((pid, "distance"))
                    self._distance_fired += 1
                    out.append(self._trigger("distance_10k", self.players[pid]["side"], pid,
                                             round(runner.distance_m), f"{self._name(pid)} passes 10 km covered"))
                    if self._distance_fired >= DISTANCE_TRIGGER_LIMIT:
                        break
        return out

    def apply_event(self, ev: dict) -> tuple[dict, list[dict]]:
        """Process one simulator event. Returns (enriched event, new triggers)."""
        self._advance(ev["t"], ev["period"])
        enriched = dict(ev)
        stats: dict = {}
        triggers: list[dict] = []
        typ = ev["type"]
        side = ev.get("team")
        pid = ev.get("player")
        pc = self.player.get(pid) if pid else None
        tc = self.team.get(side) if side else None

        if typ == "kickoff" and self.possession is None:
            self._set_possession(side, ev["t"])
        elif typ == "pass":
            stats = self._pass_stats(ev)
            pc["passes"] += 1
            tc["passes"] += 1
            if ev["outcome"] == "complete":
                pc["passes_complete"] += 1
                tc["passes_complete"] += 1
                if stats["progress_m"] > 0 and self._att_x(side, ev["to"][0]) > 70:
                    tc["final_third_passes"] += 1
                if stats["difficulty"] >= KILLER_PASS_DIFFICULTY and self._att_x(side, ev["to"][0]) > 80:
                    triggers.append(self._trigger("killer_pass", side, pid, stats["difficulty"],
                                                  f"{self._name(pid)} threads a {stats['difficulty_label']} pass "
                                                  f"to {self._name(ev['receiver'])}", [ev["id"]]))
                self._last_pass = ev
        elif typ == "shot":
            xg = shot_xg(ev)
            stats = {"xg": xg}
            pc["shots"] += 1
            tc["shots"] += 1
            pc["xg"] += xg
            tc["xg"] += xg
            if ev["outcome"] in ("goal", "saved"):
                pc["shots_on_target"] += 1
                tc["shots_on_target"] += 1
            kp = ev.get("key_pass_by")
            if kp:
                self.player[kp]["key_passes"] += 1
                self.team[side]["key_passes"] += 1
                self.player[kp]["xa"] += xg
            source = [ev["id"]] + ([self._last_pass["id"]] if self._last_pass and kp else [])
            if xg >= BIG_CHANCE_XG and ev["outcome"] != "goal":
                triggers.append(self._trigger("big_chance", side, pid, xg,
                                              f"Big chance: {self._name(pid)} ({xg:.2f} xG), {ev['outcome']}", source))
            if ev["shot_speed_kmh"] >= SHOT_TRIGGER_KMH:
                label = f"{self._name(pid)} strikes it at {ev['shot_speed_kmh']:.0f} km/h"
                triggers.append(self._trigger("shot_speed", side, pid, ev["shot_speed_kmh"], label, source))
        elif typ == "goal":
            self.score = dict(ev["score"])
            pc["goals"] += 1
            tc["goals"] += 1
            if ev.get("assist"):
                self.player[ev["assist"]]["assists"] += 1
            shot = next((e for e in reversed(self.events) if e["type"] == "shot" and e["player"] == pid), None)
            stats = {"xg": shot["stats"]["xg"]} if shot else {}
            triggers.append(self._trigger("goal", side, pid, self.score[side],
                                          f"GOAL {self.teams[side]['short']}: {self._name(pid)}",
                                          [ev["id"]] + ([shot["id"]] if shot else [])))
        elif typ == "carry":
            stats = {"progress_m": _r(self._att_x(side, ev["to"][0]) - self._att_x(side, ev["from"][0]), 1)}
            pc["carries"] += 1
            tc["carries"] += 1
        elif typ == "tackle":
            pc["tackles"] += 1
            tc["tackles"] += 1
            if ev["outcome"] == "won":
                pc["tackles_won"] += 1
                tc["tackles_won"] += 1
        elif typ in ("interception", "pressure", "clearance", "save", "block"):
            key = {"interception": "interceptions", "pressure": "pressures", "clearance": "clearances",
                   "save": "saves", "block": "blocks"}[typ]
            pc[key] += 1
            tc[key] += 1
        elif typ == "foul":
            pc["fouls"] += 1
            tc["fouls"] += 1
            if ev.get("card"):
                tc["yellow_cards"] += 1
                pc["yellow_cards"] += 1
        elif typ == "out":
            if ev["restart"] == "corner":
                self.team[other(side)]["corners"] += 1
            elif ev["restart"] == "throw_in":
                self.team[other(side)]["throw_ins"] += 1
        elif typ == "possession_change":
            self._set_possession(side, ev["t"])
        elif typ == "substitution":
            self.slots[side][ev["slot"]] = ev["player_in"]
        elif typ == "half_time":
            self.period = 2
        elif typ == "full_time":
            self._advance(ev["t"], ev["period"])
            self.finished = True

        self.control.update(ev)
        swing = self.momentum.update(ev, stats.get("xg"))
        if swing is not None and ev["t"] > 120:
            leader = swing["to"]
            triggers.append(self._trigger("momentum_swing", leader, None, swing["momentum"],
                                          f"Momentum swings to {self.teams[leader]['name']}", [ev["id"]]))
        if stats:
            enriched["stats"] = stats
        self.events.append(enriched)
        return enriched, triggers

    # ------------------------------------------------------------------
    # helpers

    def _advance(self, t: float, period: int) -> None:
        if t < self.t:
            return
        if period != self._period_seen:
            self._period_seen = period
            self._period_start = t
        secs = int(t - self._period_start) + (0 if period == 1 else 45 * 60)
        self.clock = f"{secs // 60:02d}:{secs % 60:02d}"
        if self.possession is not None:
            self.possession_time[self.possession] += t - self._poss_since
        self._poss_since = t
        minute = int(t // 60)
        if not self.history or minute > self.history[-1]["minute"]:
            self.history.append({"minute": minute, **self._trend_point()})
        self.t = t
        self.period = period

    def _set_possession(self, side: str, t: float) -> None:
        if self.possession is not None:
            self.possession_time[self.possession] += t - self._poss_since
        self.possession = side
        self._poss_since = t

    def _att_x(self, side: str, x: float) -> float:
        return x if Momentum.attack_dir(side, self.period) > 0 else 105.0 - x

    def _name(self, pid: str | None) -> str:
        return self.players[pid]["name"] if pid in self.players else "?"

    def _pass_stats(self, ev: dict) -> dict:
        side = ev["team"]
        start, end = tuple(ev["from"]), tuple(ev["to"])
        pos = self.positions()
        opponents = [pos[o] for o in self.slots[other(side)] if o in pos]
        gap = lane_gap(start, end, opponents) if opponents else 30.0
        space = receiver_space(end, opponents) if opponents else 30.0
        diff = difficulty(ev["distance_m"], ev.get("pressure", 0.0), gap, space)
        return {
            "difficulty": diff,
            "difficulty_label": difficulty_label(diff),
            "lane_gap_m": _r(gap, 1),
            "receiver_space_m": _r(space, 1),
            "progress_m": _r(self._att_x(side, end[0]) - self._att_x(side, start[0]), 1),
        }

    def _trigger(self, kind: str, side: str | None, pid: str | None, value: float, label: str,
                 source_events: list[str] | None = None) -> dict:
        self._trigger_n += 1
        tr = {"id": f"tr-{self._trigger_n:04d}", "t": self.t, "clock": self.clock, "kind": kind,
              "priority": PRIORITY[kind], "team": side, "player": pid, "value": value, "label": label,
              "source_events": source_events or []}
        self.triggers.append(tr)
        return tr

    def _trend_point(self) -> dict:
        return {
            "xg": {s: _r(self.team[s]["xg"]) for s in SIDES},
            "possession_pct": self.possession_pct(),
            "control_chaos": self.control.index(),
            "momentum": self.momentum.score,
            "field_tilt": self.momentum.field_tilt(),
        }

    # ------------------------------------------------------------------
    # output

    def possession_pct(self) -> dict[str, float]:
        total = sum(self.possession_time.values())
        if total <= 0:
            return {s: 50.0 for s in SIDES}
        return {s: round(100 * self.possession_time[s] / total, 1) for s in SIDES}

    def team_stats(self, side: str) -> dict:
        c = self.team[side]
        out = {k: int(c[k]) for k in TEAM_COUNTERS}
        out["xg"] = _r(c["xg"])
        out["goals"] = self.score[side]
        out["pass_completion_pct"] = round(100 * c["passes_complete"] / c["passes"], 1) if c["passes"] else None
        out["possession_pct"] = self.possession_pct()[side]
        out["high_turnovers"] = self.momentum.high_turnovers[side]
        out["ppda"] = self.momentum.ppda()[side]
        mine, theirs = c["final_third_passes"], self.team[other(side)]["final_third_passes"]
        out["field_tilt_pct"] = round(100 * mine / (mine + theirs), 1) if mine + theirs else 50.0
        out["distance_km"] = round(sum(self.speed.runners[p].distance_m for p in self.speed.runners
                                       if self.players[p]["side"] == side) / 1000, 1)
        return out

    def player_stats(self, pid: str) -> dict:
        c = self.player[pid]
        info = self.players[pid]
        out = {"id": pid, "name": info["name"], "number": info["number"], "position": info["position"],
               "team": info["side"], "on_pitch": pid in self.slots[info["side"]]}
        out.update({k: int(c[k]) for k in PLAYER_COUNTERS})
        out["yellow_cards"] = int(c["yellow_cards"])
        out["xg"] = _r(c["xg"])
        out["xa"] = _r(c["xa"])
        out["pass_completion_pct"] = round(100 * c["passes_complete"] / c["passes"], 1) if c["passes"] else None
        runner = self.speed.runners.get(pid)
        out.update(runner.to_dict() if runner else {"distance_m": 0, "top_speed_kmh": 0.0, "sprints": 0,
                                                    "sprint_distance_m": 0, "speed_kmh": 0.0})
        return out

    def snapshot(self) -> dict:
        """Everything an agent or the UI needs to know right now."""
        return {
            "t": self.t,
            "clock": self.clock,
            "period": self.period,
            "finished": self.finished,
            "score": dict(self.score),
            "possession": self.possession,
            "control_chaos": self.control.index(),
            "momentum": self.momentum.score,
            "field_tilt_last_5_min": self.momentum.field_tilt(),
            "teams": {s: {"name": self.teams[s]["name"], "short": self.teams[s]["short"], **self.team_stats(s)}
                      for s in SIDES},
            "recent_triggers": self.triggers[-5:],
        }

    def trend(self, metric: str, window_minutes: int = 15) -> list[dict]:
        """Per-minute history of one metric (xg, possession_pct, control_chaos, momentum, field_tilt)."""
        points = [h for h in self.history if h["minute"] >= math.floor(self.t / 60) - window_minutes]
        return [{"minute": h["minute"], "value": h[metric]} for h in points]
