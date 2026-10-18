"""Expected goals (xG) for a shot, from distance, angle, body part, situation and pressure.

A small logistic model fitted to typical public xG values: about 0.56 from
6 m, 0.28 from the penalty spot, 0.10 from the edge of the box and 0.04 from
25 m, all central and unpressured.
"""

from __future__ import annotations

import math

INTERCEPT = -0.2
PER_METRE = -0.135
PER_RADIAN = 1.15
HEADER = -0.9
PRESSURE = -0.6
SITUATION = {"open_play": 0.0, "counter": 0.2, "set_piece": -0.1}


def xg(distance_m: float, angle_deg: float, body_part: str = "foot", situation: str = "open_play",
       pressure: float = 0.0) -> float:
    logit = (INTERCEPT + PER_METRE * distance_m + PER_RADIAN * math.radians(angle_deg)
             + (HEADER if body_part == "head" else 0.0) + PRESSURE * pressure + SITUATION.get(situation, 0.0))
    return round(1.0 / (1.0 + math.exp(-logit)), 3)


def shot_xg(event: dict) -> float:
    """xG for a simulator `shot` event."""
    return xg(event["distance_m"], event["angle_deg"], event.get("body_part", "foot"),
              event.get("situation", "open_play"), event.get("pressure", 0.0))
