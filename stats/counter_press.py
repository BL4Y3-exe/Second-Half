"""Counter-pressing: does a team win the ball back within 8 seconds of losing it?

Rangnick's rule, and the moment Klopp calls the best playmaker there is. A window opens when a team loses the ball
in open play in the opponent's half. It is won if the team gets the ball back in open play before the 8 seconds are
up, though not inside a second: a ball that bounces straight back was never really lost. If not, it counts as
escaped only when the team really went after the ball, with at least three players getting within 5 m of it; a team
that drops back into shape instead was not counter-pressing.
"""

from __future__ import annotations

import math

from .momentum import Momentum

WINDOW_S = 8.0
BOUNCE_S = 1.0  # won back quicker than this, the other team never had it: the ball bounced back, nobody pressed
PRESS_RADIUS_M = 5.0  # a player this close to the ball is pressing it
PRESSERS = 3  # players that must get that close for the window to count as a counter-press
OPEN_PLAY = {"interception", "tackle", "loose_ball"}  # ways of losing (and winning) the ball in open play
HIGH_X = 52.5  # only a ball lost in the opponent's half: deeper down, a team defends rather than counter-presses


class CounterPress:
    def __init__(self) -> None:
        self.window: dict | None = None  # the team that just lost the ball: who, when, where, how many pressed
        self.records: list[dict] = []  # every counter-press, won or escaped, in order
        self.feed: list[dict] = []  # for the browser: each window as it opens, then its record if it is one
        self.presses = {"HOME": 0, "AWAY": 0}
        self.wins = {"HOME": 0, "AWAY": 0}
        self._holder: str | None = None
        self._n = 0

    def event(self, ev: dict, clock: str) -> dict | None:
        """Feed every match event. Returns the record when this event wins the ball back in time."""
        won = None
        if ev["type"] == "possession_change":
            side, w = ev.get("team"), self.window
            if (w is not None and side == w["team"] and ev.get("reason") in OPEN_PLAY
                    and BOUNCE_S <= ev["t"] - w["t"] <= WINDOW_S):
                won = self._close(w, ev["t"], clock, "won", ev["at"], ev["id"], ev.get("player"))
            self.window = None
            if ev.get("reason") in OPEN_PLAY and self._holder not in (None, side) and self._high(ev):
                self._n += 1
                self.window = {"id": f"cp-{self._n:04d}", "team": self._holder, "t": ev["t"], "period": ev["period"],
                               "pressers": set()}
                self.feed.append({"id": self.window["id"], "team": self._holder, "t": round(ev["t"], 1),
                                  "lost_t": round(ev["t"], 1), "clock": clock, "period": ev["period"],
                                  "outcome": "open", "seconds": 0.0,
                                  "at": [round(ev["at"][0], 1), round(ev["at"][1], 1)], "pressers": 0,
                                  "event": None, "player": None})
            self._holder = side
        elif ev["type"] in ("half_time", "full_time", "goal", "kickoff"):
            self.window = None
        return won

    def _high(self, ev: dict) -> bool:
        x = ev["at"][0] if Momentum.attack_dir(self._holder, ev["period"]) > 0 else 105.0 - ev["at"][0]
        return x > HIGH_X

    def frame(self, t: float, ball: tuple[float, float], players: dict[str, tuple[float, float]],
              clock: str) -> dict | None:
        """Feed every frame with the positions of the team without the ball (in the window). Returns the record
        when the 8 seconds run out on a team that pressed."""
        w = self.window
        if w is None:
            return None
        if t - w["t"] > WINDOW_S:
            self.window = None
            if len(w["pressers"]) >= PRESSERS:
                return self._close(w, t, clock, "escaped", ball, None, None)
            return None
        for pid, xy in players.items():
            if math.dist(xy, ball) <= PRESS_RADIUS_M:
                w["pressers"].add(pid)
        return None

    def _close(self, w: dict, t: float, clock: str, outcome: str, at, event_id: str | None,
               player: str | None) -> dict:
        side = w["team"]
        self.presses[side] += 1
        if outcome == "won":
            self.wins[side] += 1
        rec = {"id": w["id"], "team": side, "t": round(t, 1), "lost_t": round(w["t"], 1),
               "clock": clock, "period": w["period"], "outcome": outcome,
               "seconds": round(t - w["t"], 1), "at": [round(at[0], 1), round(at[1], 1)],
               "pressers": len(w["pressers"]), "event": event_id, "player": player}
        self.records.append(rec)
        self.feed.append(rec)
        return rec

    def stats(self, side: str) -> dict:
        n, won = self.presses[side], self.wins[side]
        return {"counter_presses": n, "counter_press_wins": won,
                "counter_press_win_pct": round(100 * won / n, 1) if n else None}
