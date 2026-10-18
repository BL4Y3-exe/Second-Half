"""Momentum and pressure: field tilt, high turnovers, PPDA and a rolling momentum score."""

from __future__ import annotations

import math
from collections import deque

WINDOW_S = 300.0
SIDES = ("HOME", "AWAY")
DEFENSIVE_ACTIONS = {"tackle", "interception", "foul"}


def other(side: str) -> str:
    return "AWAY" if side == "HOME" else "HOME"


class Momentum:
    """Needs to know which way each team attacks: attack_dir(side, period) -> +1 (towards x=105) or -1."""

    def __init__(self, window_s: float = WINDOW_S) -> None:
        self.window = window_s
        self.final_third: deque[tuple[float, str]] = deque()  # passes completed into the final third
        self.threat: deque[tuple[float, str, float]] = deque()  # (t, side, weight)
        self.high_turnovers = {s: 0 for s in SIDES}
        self.ppda_passes = {s: 0 for s in SIDES}  # opponent passes in their own 60%, faced by side
        self.ppda_actions = {s: 0 for s in SIDES}  # side's defensive actions in the opponent's 60%
        self.score = 0.0  # -100 (AWAY on top) .. +100 (HOME on top)
        self.leader: str | None = None

    @staticmethod
    def attack_dir(side: str, period: int) -> int:
        return 1 if (side == "HOME") == (period == 1) else -1

    def _att_x(self, side: str, period: int, x: float) -> float:
        return x if self.attack_dir(side, period) > 0 else 105.0 - x

    def update(self, ev: dict, xg: float | None = None) -> dict | None:
        """Returns a swing record when the team on top changes decisively."""
        t, typ, side, period = ev["t"], ev["type"], ev.get("team"), ev["period"]
        if side not in SIDES:
            return None
        if typ == "pass":
            start_x = self._att_x(side, period, ev["from"][0])
            if start_x < 63:  # own 60% of the pitch
                self.ppda_passes[other(side)] += 1
            if ev["outcome"] == "complete" and self._att_x(side, period, ev["to"][0]) > 70:
                self.final_third.append((t, side))
                self.threat.append((t, side, 0.02))
        elif typ == "shot":
            self.threat.append((t, side, 0.05 + (xg or 0.0)))
        elif typ == "carry" and self._att_x(side, period, ev["to"][0]) > 75:
            self.threat.append((t, side, 0.015))
        elif typ == "out" and ev.get("restart") == "corner":
            self.threat.append((t, other(side), 0.03))
        if typ in DEFENSIVE_ACTIONS and "at" in ev and self._att_x(side, period, ev["at"][0]) > 42:
            self.ppda_actions[side] += 1
        if typ == "possession_change" and "at" in ev and self._att_x(side, period, ev["at"][0]) > 65:
            self.high_turnovers[side] += 1
            self.threat.append((t, side, 0.02))
        self._trim(t)
        return self._rescore(t)

    def _trim(self, now: float) -> None:
        cut = now - self.window
        while self.final_third and self.final_third[0][0] < cut:
            self.final_third.popleft()
        while self.threat and self.threat[0][0] < cut:
            self.threat.popleft()

    def _rescore(self, now: float) -> dict | None:
        # Recent actions count more: exponential decay with a 2-minute half-life.
        net = 0.0
        for t, side, w in self.threat:
            decay = math.exp(-(now - t) * math.log(2) / 120.0)
            net += w * decay * (1 if side == "HOME" else -1)
        self.score = round(100 * math.tanh(net / 0.25), 1)
        leader = "HOME" if self.score > 35 else "AWAY" if self.score < -35 else None
        swing = None
        if leader is not None and leader != self.leader:
            swing = {"to": leader, "momentum": self.score, "from": self.leader}
        if leader is not None:
            self.leader = leader
        return swing

    def field_tilt(self) -> dict[str, float]:
        """Share of final-third passes in the window, per team (percent)."""
        n = len(self.final_third)
        if n == 0:
            return {s: 50.0 for s in SIDES}
        home = sum(1 for _t, s in self.final_third if s == "HOME")
        return {"HOME": round(100 * home / n, 1), "AWAY": round(100 * (n - home) / n, 1)}

    def ppda(self) -> dict[str, float | None]:
        """Passes allowed per defensive action (lower = more intense pressing)."""
        return {s: round(self.ppda_passes[s] / self.ppda_actions[s], 1) if self.ppda_actions[s] else None
                for s in SIDES}
