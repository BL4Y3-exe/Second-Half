"""Spotter: watches the stats engine's triggers and flags candidate key moments.

It waits 1.5 s of match time before flagging, so a shot that goes in becomes
a goal moment rather than a shot-speed moment, and it keeps the broadcast
from cluttering: priority 1 always goes through, lower priorities need a gap
since the last moment.
"""

from __future__ import annotations

from .types import Moment

SETTLE_S = 1.5
GAP_S = {2: 40.0, 3: 120.0}  # match seconds since the last flagged moment
KIND_GAP_S = {"killer_pass": 480.0, "momentum_swing": 240.0, "sprint_speed": 600.0, "shot_speed": 120.0}


class Spotter:
    name = "spotter"

    def __init__(self) -> None:
        self.pending: list[dict] = []
        self.last_t = -1e9
        self.last_kind_t: dict[str, float] = {}
        self._n = 0

    def watch(self, trigger: dict) -> None:
        self.pending.append(trigger)

    def recap(self, label: str, t: float, clock: str) -> Moment:
        self._n += 1
        return Moment(f"m-{self._n:03d}", "recap", t, clock, 1, None, None, label, {"kind": "recap", "label": label})

    def release(self, now: float) -> list[tuple[Moment | None, dict, str]]:
        """Triggers that have settled: (moment or None if passed over, trigger, reason)."""
        ready = [tr for tr in self.pending if now - tr["t"] >= SETTLE_S]
        if not ready:
            return []
        self.pending = [tr for tr in self.pending if now - tr["t"] < SETTLE_S]
        # The goal trigger comes a moment after the shot's own triggers, so it may still be settling.
        goal_shots = {e for tr in ready + self.pending if tr["kind"] == "goal" for e in tr["source_events"]}
        out: list[tuple[Moment | None, dict, str]] = []
        for tr in sorted(ready, key=lambda r: (r["t"], r["priority"])):
            reason = self._reject_reason(tr, goal_shots)
            if reason:
                out.append((None, tr, reason))
                continue
            self._n += 1
            self.last_t = tr["t"]
            self.last_kind_t[tr["kind"]] = tr["t"]
            out.append((Moment(
                id=f"m-{self._n:03d}", kind=tr["kind"], t=tr["t"], clock=tr["clock"], priority=tr["priority"],
                team=tr["team"], player=tr["player"], label=tr["label"], trigger=tr,
                source_events=list(tr["source_events"]),
            ), tr, "flagged"))
        return out

    def _reject_reason(self, tr: dict, goal_shots: set[str]) -> str | None:
        if tr["kind"] != "goal" and set(tr["source_events"]) & goal_shots:
            return "part of a goal moment"
        if tr["priority"] == 1:
            return None
        if tr["t"] - self.last_t < GAP_S.get(tr["priority"], 60.0):
            return "too soon after the last moment"
        if tr["t"] - self.last_kind_t.get(tr["kind"], -1e9) < KIND_GAP_S.get(tr["kind"], 0.0):
            return f"already showed a {tr['kind'].replace('_', ' ')} recently"
        return None
