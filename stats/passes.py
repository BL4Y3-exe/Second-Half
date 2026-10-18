"""Pass quality: how hard a pass was, from distance, pressure and how open the lane was."""

from __future__ import annotations

import math

Vec = tuple[float, float]


def _point_segment(p: Vec, a: Vec, b: Vec) -> tuple[float, float]:
    abx, aby = b[0] - a[0], b[1] - a[1]
    ab2 = abx * abx + aby * aby
    if ab2 == 0:
        return math.dist(p, a), 0.0
    f = max(0.0, min(1.0, ((p[0] - a[0]) * abx + (p[1] - a[1]) * aby) / ab2))
    return math.dist(p, (a[0] + abx * f, a[1] + aby * f)), f


def lane_gap(start: Vec, end: Vec, opponents: list[Vec]) -> float:
    """Closest an opponent stands to the passing lane, ignoring the first 2 m (that is pressure)."""
    length = max(math.dist(start, end), 0.1)
    best = 30.0
    for o in opponents:
        d, f = _point_segment(o, start, end)
        if f * length > 2.0:
            best = min(best, d)
    return best


def receiver_space(end: Vec, opponents: list[Vec]) -> float:
    return min((math.dist(end, o) for o in opponents), default=30.0)


def difficulty(distance_m: float, passer_pressure: float, lane_gap_m: float, receiver_space_m: float) -> float:
    """0 (trivial) to 1 (very hard)."""
    dist_part = min(1.0, distance_m / 45.0)
    lane_part = 1.0 - min(1.0, max(0.0, (lane_gap_m - 0.5) / 4.0))
    space_part = 1.0 - min(1.0, max(0.0, (receiver_space_m - 1.0) / 5.0))
    score = 0.35 * dist_part + 0.2 * passer_pressure + 0.3 * lane_part + 0.15 * space_part
    return round(max(0.0, min(1.0, score)), 2)


def difficulty_label(d: float) -> str:
    return "easy" if d < 0.3 else "medium" if d < 0.5 else "hard" if d < 0.7 else "very hard"
