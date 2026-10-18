"""Running stats from position frames: speed, distance covered, sprints."""

from __future__ import annotations

import math
from dataclasses import dataclass

SPRINT_KMH = 25.0
MAX_PLAUSIBLE_KMH = 40.0  # anything faster between frames is a substitution or a reset, not running


@dataclass
class Runner:
    distance_m: float = 0.0
    top_speed_kmh: float = 0.0
    sprints: int = 0
    sprint_distance_m: float = 0.0
    speed_kmh: float = 0.0
    _sprinting_for: float = 0.0
    _counted: bool = False

    def to_dict(self) -> dict:
        return {
            "distance_m": round(self.distance_m),
            "top_speed_kmh": round(self.top_speed_kmh, 1),
            "sprints": self.sprints,
            "sprint_distance_m": round(self.sprint_distance_m),
            "speed_kmh": round(self.speed_kmh, 1),
        }


class SpeedTracker:
    """Feed frames in order; keeps per-player running stats keyed by player id."""

    def __init__(self) -> None:
        self.runners: dict[str, Runner] = {}
        self._last: dict[str, tuple[float, tuple[float, float]]] = {}
        self._period = 1

    def update(self, t: float, positions: dict[str, tuple[float, float]],
               period: int = 1) -> list[tuple[str, str, float]]:
        """Returns new records as (player_id, kind, value): kind is 'top_speed' or 'sprint'."""
        if period != self._period:  # players are lined up again at half time: not running
            self._period = period
            self._last = {}
        records = []
        for pid, pos in positions.items():
            r = self.runners.setdefault(pid, Runner())
            last = self._last.get(pid)
            self._last[pid] = (t, pos)
            if last is None or t <= last[0]:
                continue
            dt = t - last[0]
            d = math.dist(pos, last[1])
            kmh = d / dt * 3.6
            if kmh > MAX_PLAUSIBLE_KMH or dt > 2.0:
                continue
            r.distance_m += d
            r.speed_kmh = kmh
            if kmh > r.top_speed_kmh:
                r.top_speed_kmh = kmh
                records.append((pid, "top_speed", kmh))
            if kmh >= SPRINT_KMH:
                r.sprint_distance_m += d
                r._sprinting_for += dt
                if r._sprinting_for >= 1.0 and not r._counted:
                    r.sprints += 1
                    r._counted = True
                    records.append((pid, "sprint", kmh))
            else:
                r._sprinting_for = 0.0
                r._counted = False
        return records
