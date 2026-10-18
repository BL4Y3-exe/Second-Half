"""Movement, ball flight and geometry helpers. Units: metres and seconds."""

from __future__ import annotations

import math

Vec = tuple[float, float]

ACCELERATION = 5.0  # m/s^2


def dist(a: Vec, b: Vec) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def lerp(a: Vec, b: Vec, f: float) -> Vec:
    return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f


def top_speed(pace: int, energy: float) -> float:
    """Top running speed in m/s: about 29 km/h for pace 50, 34 km/h for pace 95, less when tired."""
    return (6.9 + 2.6 * pace / 100) * (0.82 + 0.18 * energy)


def step(pos: Vec, vel: Vec, target: Vec, desired_speed: float, dt: float) -> tuple[Vec, Vec]:
    """Move towards target with limited acceleration; returns (new_pos, new_vel)."""
    dx, dy = target[0] - pos[0], target[1] - pos[1]
    d = math.hypot(dx, dy)
    if d < 0.05:
        want = (0.0, 0.0)
    else:
        speed = min(desired_speed, d * 1.5)  # ease off when arriving
        want = (dx / d * speed, dy / d * speed)
    ax, ay = want[0] - vel[0], want[1] - vel[1]
    a = math.hypot(ax, ay)
    limit = ACCELERATION * dt
    if a > limit:
        ax, ay = ax / a * limit, ay / a * limit
    nvel = (vel[0] + ax, vel[1] + ay)
    npos = (pos[0] + nvel[0] * dt, pos[1] + nvel[1] * dt)
    return npos, nvel


def pass_speed(distance: float) -> float:
    """Typical ball speed (m/s) for a pass of this length."""
    return max(9.0, min(27.0, 9.0 + 0.42 * distance))


def point_segment(p: Vec, a: Vec, b: Vec) -> tuple[float, float]:
    """Distance from p to segment ab, and how far along ab (0..1) the closest point is."""
    abx, aby = b[0] - a[0], b[1] - a[1]
    ab2 = abx * abx + aby * aby
    if ab2 == 0:
        return dist(p, a), 0.0
    f = max(0.0, min(1.0, ((p[0] - a[0]) * abx + (p[1] - a[1]) * aby) / ab2))
    return dist(p, (a[0] + abx * f, a[1] + aby * f)), f


def goal_angle(pos: Vec, goal_x: float = 105.0, post_low: float = 30.34, post_high: float = 37.66) -> float:
    """Angle (radians) subtended by the goal mouth from pos."""
    a1 = math.atan2(post_low - pos[1], goal_x - pos[0])
    a2 = math.atan2(post_high - pos[1], goal_x - pos[0])
    return abs(a2 - a1)


def shot_quality(distance: float, angle: float, pressure: float, header: bool) -> float:
    """Chance an average finisher scores against an average keeper (the same curve the stats engine uses for xG)."""
    logit = -0.2 - 0.135 * distance + 1.15 * angle - (0.9 if header else 0.0) - 0.6 * pressure
    return 1.0 / (1.0 + math.exp(-logit))


def position_value(pos: Vec) -> float:
    """Rough chance that holding the ball here (attacking frame) ends in a goal."""
    d = math.hypot(105.0 - pos[0], 34.0 - pos[1])
    centrality = 1.0 - min(1.0, abs(pos[1] - 34.0) / 34.0) * 0.5
    return 0.01 + 0.45 * math.exp(-d / 10.0) * centrality
