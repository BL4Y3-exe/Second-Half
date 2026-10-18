"""Team styles, formations and where each player wants to stand.

All positions here are in a team's *attacking frame*: the team attacks
towards x = 105, so its own goal is at x = 0. The engine converts to and
from real pitch coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0


@dataclass(frozen=True)
class Style:
    name: str
    press_line: float  # metres the out-of-possession block is pushed up (+) or dropped (-)
    press_trigger: float  # distance from the ball at which the nearest defender engages
    attack_push: float  # metres the in-possession block is pushed up
    tempo: float  # typical seconds a carrier keeps the ball before acting
    directness: float  # preference for forward passes and long balls
    risk: float  # appetite for low-percentage passes
    width: float  # how wide the team stretches in possession
    shoot_bias: float  # willingness to shoot rather than work a better chance


STYLES: dict[str, Style] = {
    "high_press": Style("high_press", press_line=9, press_trigger=15, attack_push=8, tempo=1.2,
                        directness=0.6, risk=0.55, width=1.05, shoot_bias=1.0),
    "possession": Style("possession", press_line=4, press_trigger=10, attack_push=10, tempo=1.5,
                        directness=0.2, risk=0.3, width=1.15, shoot_bias=0.9),
    "counter": Style("counter", press_line=-8, press_trigger=7, attack_push=3, tempo=1.1,
                     directness=1.0, risk=0.7, width=0.95, shoot_bias=1.15),
}

# (position code, x, y) per slot, in the attacking frame, for a mid block
# with the ball on the centre spot. Slot 0 is always the goalkeeper.
FORMATIONS: dict[str, list[tuple[str, float, float]]] = {
    "4-3-3": [
        ("GK", 4, 34), ("LB", 24, 8), ("CB", 18, 25), ("CB", 18, 43), ("RB", 24, 60),
        ("DM", 32, 34), ("CM", 42, 22), ("CM", 42, 46),
        ("LW", 58, 9), ("ST", 62, 34), ("RW", 58, 59),
    ],
    "4-2-3-1": [
        ("GK", 4, 34), ("LB", 24, 8), ("CB", 18, 25), ("CB", 18, 43), ("RB", 24, 60),
        ("DM", 33, 26), ("DM", 33, 42),
        ("LW", 52, 10), ("AM", 50, 34), ("RW", 52, 58), ("ST", 62, 34),
    ],
    "4-4-2": [
        ("GK", 4, 34), ("LB", 22, 9), ("CB", 17, 26), ("CB", 17, 42), ("RB", 22, 59),
        ("LM", 40, 10), ("CM", 37, 27), ("CM", 37, 41), ("RM", 40, 58),
        ("ST", 58, 28), ("ST", 58, 40),
    ],
}

GROUPS = {
    "GK": "GK",
    "LB": "DEF", "RB": "DEF", "CB": "DEF",
    "DM": "MID", "CM": "MID", "AM": "MID", "LM": "MID", "RM": "MID",
    "LW": "FWD", "RW": "FWD", "ST": "FWD",
}


def role_group(code: str) -> str:
    return GROUPS[code]


@dataclass(frozen=True)
class Mods:
    """Game-state adjustments on top of a team's style (score, clock, confidence)."""

    push: float = 0.0
    press: float = 0.0
    risk: float = 0.0
    tempo: float = 1.0


def shape_target(
    code: str,
    base: tuple[float, float],
    ball: tuple[float, float],
    in_possession: bool,
    style: Style,
    mods: Mods,
) -> tuple[float, float]:
    """Where a player wants to stand, given the ball, in the attacking frame."""
    bx, by = base
    ball_x, ball_y = ball
    if code == "GK":
        x = 4.0 + max(0.0, ball_x - 50) * 0.12 if in_possession else 3.0 + max(0.0, ball_x - 30) * 0.05
        y = 34 + (ball_y - 34) * 0.15
        return x, y

    group = GROUPS[code]
    if in_possession:
        shift = 0.55 * (ball_x - 40) + style.attack_push + mods.push
        x = bx + shift
        y = 34 + (by - 34) * style.width * 1.1 + (ball_y - 34) * 0.2
        cap = {"DEF": 72.0, "MID": 90.0, "FWD": 98.0}[group]
        floor = {"DEF": 10.0, "MID": 18.0, "FWD": 30.0}[group]
    else:
        shift = 0.5 * (ball_x - 52.5) + style.press_line + mods.press
        x = bx * 0.9 + shift
        y = 34 + (by - 34) * 0.8 + (ball_y - 34) * 0.35
        cap = {"DEF": 55.0, "MID": 75.0, "FWD": 90.0}[group]
        floor = {"DEF": 6.0, "MID": 12.0, "FWD": 25.0}[group]
        # Defenders and midfielders get back goal-side of the ball.
        if group != "FWD":
            gap = 6.0 if group == "DEF" else 2.0
            x = min(x, max(floor, ball_x - gap))
            y = y + (ball_y - y) * (0.25 if ball_x < 35 else 0.0)  # squeeze towards the ball near goal
    x = max(floor, min(cap, x))
    y = max(2.0, min(PITCH_WIDTH - 2.0, y))
    return x, y
