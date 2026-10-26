"""Average shape: where each player stands on average with the ball and without it, half by half.

Every position frame of play counts, by lineup slot (a substitute takes over his slot), in the team's attacking
direction: x is metres from its own goal line and y runs from its left touchline, so both teams and both halves
read the same way. The formation is read off the outfield players' average depths: sorted from the back, a new
line starts wherever the next player is more than 6 m further up. A 4-3-3 with a holding midfielder reads 4-1-2-3.
"""

from __future__ import annotations

from .momentum import Momentum

SIDES = ("HOME", "AWAY")
LINE_GAP_M = 6.0


def formation(depths: list[float]) -> str:
    """The lines, from the back, that a set of outfield players' depths make: "4-4-2"."""
    xs = sorted(depths)
    sizes = [1]
    for prev, x in zip(xs, xs[1:], strict=False):
        if x - prev > LINE_GAP_M:
            sizes.append(1)
        else:
            sizes[-1] += 1
    return "-".join(map(str, sizes))


class ShapeTracker:
    def __init__(self) -> None:
        self._sums: dict[tuple[int, str, bool], list[list[float]]] = {}  # (period, side, with ball) -> per slot
        self._frames: dict[tuple[int, str, bool], int] = {}

    def frame(self, period: int, possession: str | None, players: list[list[float]]) -> None:
        """Feed every position frame: players are home slots 0-10 then away slots 0-10."""
        if possession not in SIDES:
            return
        for k, side in enumerate(SIDES):
            key = (period, side, possession == side)
            sums = self._sums.setdefault(key, [[0.0, 0.0] for _ in range(11)])
            forward = Momentum.attack_dir(side, period) > 0
            for slot, (x, y) in enumerate(players[11 * k:11 * k + 11]):
                sums[slot][0] += x if forward else 105.0 - x
                sums[slot][1] += y if forward else 68.0 - y
            self._frames[key] = self._frames.get(key, 0) + 1

    def shape(self, period: int, side: str, with_ball: bool) -> dict | None:
        """A team's average shape in one half, with the ball or without it: the positions by slot (goalkeeper
        first), the formation, how high the back line sat and how long the team was, back to front."""
        n = self._frames.get((period, side, with_ball))
        if not n:
            return None
        positions = [[round(x / n, 1), round(y / n, 1)] for x, y in self._sums[(period, side, with_ball)]]
        depths = [x for x, _ in positions[1:]]
        shape = formation(depths)
        back = sorted(depths)[:int(shape.split("-")[0])]
        return {"positions": positions, "formation": shape, "back_line_m": round(sum(back) / len(back)),
                "length_m": round(max(depths) - min(depths))}
