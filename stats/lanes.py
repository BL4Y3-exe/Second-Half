"""The five lanes of positional play: two wings, two half-spaces and the centre.

The lines between them run the length of the pitch along the sides of the penalty area and of the six-yard box.
The half-spaces are the strips in between: a player who gets the ball there in the final third can shoot, slip a
pass inside or go wide, which is why coaches want it there. A lane is named from the attacking team's side: its
left wing is on its left as it attacks. The pitch is drawn with y = 0 along the top touchline, so a team attacking
to the right (towards x = 105) has its left wing along the top.
"""

from __future__ import annotations

EDGES = (13.84, 24.84, 43.16, 54.16)  # y of the lane lines: a 40.32 m penalty area and an 18.32 m six-yard box
LANES = ("left_wing", "left_half_space", "centre", "right_half_space", "right_wing")
HALF_SPACES = ("left_half_space", "right_half_space")
FINAL_THIRD_X = 70.0  # metres from the team's own goal line


def lane(y: float, attack_dir: int) -> str:
    """The lane at width y for a team attacking towards x = 105 (attack_dir 1) or towards x = 0 (-1)."""
    i = sum(y >= e for e in EDGES)
    return LANES[i] if attack_dir > 0 else LANES[len(LANES) - 1 - i]


def empty() -> dict[str, int]:
    return dict.fromkeys(LANES, 0)
