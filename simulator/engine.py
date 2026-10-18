"""Synthetic match engine.

Ticks every 0.1 s of match time, moving all 22 players and the ball, and
emits match events (pass, carry, shot, tackle, interception, foul,
possession change, pressure, substitution, goal, ...). The same seed always
produces the same match.

Pitch coordinates are metres on a 105 x 68 pitch, origin at a corner. The
home team attacks towards x = 105 in the first half and towards x = 0 in
the second.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterator
from dataclasses import dataclass, field

from . import physics as ph
from .tactics import FORMATIONS, PITCH_LENGTH, PITCH_WIDTH, STYLES, Mods, shape_target
from .teams import Player, Team

DT = 0.1
TICKS_PER_SECOND = 10
HALF_SECONDS = 45 * 60
GOAL_POSTS = (30.34, 37.66)
SIDES = ("HOME", "AWAY")
RESTART_PAUSE = {
    "throw_in": (7, 14), "goal_kick": (12, 20), "corner": (16, 26), "free_kick": (10, 22),
    "keeper": (4, 9), "kickoff": (35, 55),
}
KEEP = 0.06  # value of simply having the ball, on top of field position


def other(side: str) -> str:
    return "AWAY" if side == "HOME" else "HOME"


def _r(v: float) -> float:
    return round(v, 1)


def _just_off_pitch(p: ph.Vec) -> ph.Vec:
    """A ball going out stops just past the line rather than flying into the stands."""
    return max(-1.5, min(PITCH_LENGTH + 1.5, p[0])), max(-1.5, min(PITCH_WIDTH + 1.5, p[1]))


def _pt(p: ph.Vec) -> list[float]:
    return [_r(p[0]), _r(p[1])]


@dataclass
class PState:
    """A player on the pitch."""

    player: Player
    side: str
    slot: int
    pos: ph.Vec
    vel: ph.Vec = (0.0, 0.0)
    energy: float = 1.0
    distance: float = 0.0
    top_speed: float = 0.0  # fastest observed, m/s
    sprint_distance: float = 0.0
    run_offset: ph.Vec = (0.0, 0.0)
    run_offset_until: float = 0.0
    override: ph.Vec | None = None
    override_until: float = 0.0
    beaten_until: float = 0.0

    @property
    def id(self) -> str:
        return self.player.id

    @property
    def code(self) -> str:
        return self.player.position


@dataclass
class Flight:
    kind: str  # "pass" or "shot"
    start: ph.Vec
    end: ph.Vec
    t0: float
    duration: float
    outcome: str
    passer: PState
    receiver: PState | None = None
    cross: bool = False


@dataclass
class Loose:
    """The ball is free at `spot`; the first player to reach it takes it."""

    spot: ph.Vec
    last_touch: str
    since: float
    reserved: PState | None = None  # pass receiver or interceptor, who gets first claim
    reason: str | None = None  # possession-change reason if the reserved player collects


@dataclass
class Restart:
    kind: str  # kickoff, throw_in, goal_kick, corner, free_kick, keeper
    side: str
    spot: ph.Vec
    taker: PState
    until: float


@dataclass
class Tick:
    t: float
    period: int
    events: list[dict] = field(default_factory=list)
    frame: dict | None = None


class MatchEngine:
    def __init__(self, home: Team, away: Team, seed: int = 0, frame_step: float = 0.1):
        if home.side != "HOME" or away.side != "AWAY":
            raise ValueError("home must be built with side HOME and away with side AWAY")
        self.teams = {"HOME": home, "AWAY": away}
        self.seed = seed
        self.rng = random.Random(seed)
        self.styles = {s: STYLES[t.style] for s, t in self.teams.items()}
        self.formations = {s: FORMATIONS[t.formation] for s, t in self.teams.items()}
        self.frame_every = max(1, round(frame_step * TICKS_PER_SECOND))

        self.on_pitch: dict[str, list[PState]] = {}
        self.bench: dict[str, list[Player]] = {}
        self.all_players: dict[str, PState] = {}
        for side, team in self.teams.items():
            self.on_pitch[side] = [PState(p, side, i, (52.5, 34.0)) for i, p in enumerate(team.starters)]
            self.bench[side] = list(team.bench)
            for ps in self.on_pitch[side]:
                self.all_players[ps.id] = ps
        self.lineups: list[dict] = [self._lineup_snapshot()]

        self.tick_n = 0
        self.t = 0.0
        self.period = 1
        self.period_start = 0.0
        self.stoppage = {1: self.rng.randint(60, 240), 2: self.rng.randint(120, 330)}
        self.first_kickoff = self.rng.choice(SIDES)
        self.finished = False

        self.score = {"HOME": 0, "AWAY": 0}
        self.events: list[dict] = []
        self._pending: list[dict] = []
        self._event_n = 0

        self.ball: ph.Vec = (52.5, 34.0)
        self.ball_seen: ph.Vec = (52.5, 34.0)  # lagged ball position the team shape reacts to
        self.spell_start = 0.0
        self.possession: str | None = None
        self.carrier: PState | None = None
        self.carry_target: ph.Vec | None = None
        self.carry_start: tuple[ph.Vec, float] | None = None
        self.flight: Flight | None = None
        self.loose: Loose | None = None
        self.restart: Restart | None = None
        self.next_decision = 0.0
        self.force_cross = False
        self.set_piece_until = 0.0
        self.pressed: set[str] = set()
        self.tackle_ready_at = 0.0
        self.last_pass: dict | None = None  # last completed pass, for assists and headers
        self.transition_until = 0.0

        self.subs_made = {s: 0 for s in SIDES}
        self.sub_times = {s: sorted(self.rng.sample(range(56 * 60, 84 * 60, 60), 3)) for s in SIDES}
        self.confidence = {s: 0.0 for s in SIDES}
        self.possession_time = {s: 0.0 for s in SIDES}

    # ------------------------------------------------------------------
    # coordinates and clock

    def attack_dir(self, side: str) -> int:
        return 1 if (side == "HOME") == (self.period == 1) else -1

    def to_att(self, side: str, p: ph.Vec) -> ph.Vec:
        """Real pitch coordinates to the side's attacking frame (and back: it is its own inverse)."""
        if self.attack_dir(side) > 0:
            return p
        return PITCH_LENGTH - p[0], PITCH_WIDTH - p[1]

    def clock_seconds(self) -> float:
        return (self.t - self.period_start) + (0 if self.period == 1 else HALF_SECONDS)

    def clock(self) -> str:
        s = int(self.clock_seconds())
        return f"{s // 60:02d}:{s % 60:02d}"

    def minute(self) -> int:
        return int(self.clock_seconds() // 60) + 1

    def offside_line(self, side: str) -> float:
        """Furthest x (attacking frame) an attacker of `side` can stand without being offside."""
        xs = sorted((self.to_att(side, o.pos)[0] for o in self.on_pitch[other(side)]), reverse=True)
        ball_x = self.to_att(side, self.ball)[0]
        return max(xs[1], ball_x, 52.5)

    # ------------------------------------------------------------------
    # events

    def emit(self, type_: str, **fields) -> dict:
        self._event_n += 1
        ev = {"id": f"e-{self._event_n:05d}", "t": _r(self.t), "period": self.period, "clock": self.clock(),
              "type": type_}
        ev.update(fields)
        self.events.append(ev)
        self._pending.append(ev)
        return ev

    def _lineup_snapshot(self) -> dict:
        return {"t": _r(getattr(self, "t", 0.0)), **{s: [p.id for p in self.on_pitch[s]] for s in SIDES}}

    # ------------------------------------------------------------------
    # main loop

    def run(self) -> Iterator[Tick]:
        """Yield one Tick per 0.1 s until full time."""
        self._kickoff(self.first_kickoff, initial=True)
        yield Tick(self.t, self.period, self._flush(), self._frame())
        while not self.finished:
            self._tick()
            frame = self._frame() if self.tick_n % self.frame_every == 0 or self.finished else None
            yield Tick(self.t, self.period, self._flush(), frame)

    def simulate(self) -> dict:
        """Run the whole match and return events, frames and metadata."""
        frames = []
        for tick in self.run():
            if tick.frame is not None:
                frames.append(tick.frame)
        return {"events": self.events, "frames": frames, "lineups": self.lineups}

    def _flush(self) -> list[dict]:
        out, self._pending = self._pending, []
        return out

    def _frame(self) -> dict:
        players = [_pt(p.pos) for s in SIDES for p in self.on_pitch[s]]
        return {
            "t": _r(self.t),
            "period": self.period,
            "b": _pt(self.ball),
            "p": players,
            "o": self.carrier.id if self.carrier else None,
        }

    def _tick(self) -> None:
        self.tick_n += 1
        self.t = self.tick_n / TICKS_PER_SECOND

        if self.restart is not None:
            if self.t >= self.restart.until:
                self._take_restart()
        elif self.flight is not None:
            self._advance_flight()
        elif self.loose is not None:
            self._collect_loose()
        elif self.carrier is not None:
            if (self.t >= self.next_decision
                    or (self.t - self.spell_start > 0.5 and self._pressure(self.carrier) > 0.7
                        and self.rng.random() < 0.2)):
                self._decide()
            if self.carrier is not None and self.flight is None and self.restart is None:
                self._defend()

        self._move_players()
        if self.carrier is not None and self.flight is None:
            c = self.carrier
            self.ball = (c.pos[0] + c.vel[0] * 0.08, c.pos[1] + c.vel[1] * 0.08)
        if self.possession is not None and self.restart is None:
            self.possession_time[self.possession] += DT

        self._check_period_end()

    # ------------------------------------------------------------------
    # game state

    def _mods(self, side: str) -> Mods:
        minute = self.minute()
        diff = self.score[side] - self.score[other(side)]
        push = press = risk = 0.0
        tempo = 1.0
        if diff < 0 and minute >= 60:
            push, press, risk, tempo = 5.0, 6.0, 0.25 + 0.1 * min(2, -diff), 0.85
        elif diff > 0 and minute >= 70:
            push, press, risk, tempo = -6.0, -7.0, -0.15, 1.2
        conf = self.confidence[side]
        push += 3.0 * conf
        return Mods(push=push, press=press, risk=risk, tempo=tempo)

    def _pressure(self, c: PState) -> float:
        d = min(ph.dist(o.pos, c.pos) for o in self.on_pitch[other(c.side)])
        return max(0.0, min(1.0, (4.0 - d) / 3.0))

    def _bump_confidence(self, side: str, amount: float) -> None:
        self.confidence[side] = max(-1.0, min(1.0, self.confidence[side] * 0.97 + amount))

    # ------------------------------------------------------------------
    # restarts and kickoffs

    def _kickoff(self, side: str, initial: bool = False, teleport: bool = True, pause: float = 1.0) -> None:
        """Line up for a kickoff. At the start of a half players are placed; after a goal they walk back."""
        self.flight = None
        self.loose = None
        self.carrier = None
        self.carry_target = None
        self.ball = (52.5, 34.0)
        taker = self._kickoff_taker(side)
        if teleport:
            self.ball_seen = self.ball
            for s in SIDES:
                for p in self.on_pitch[s]:
                    p.pos = self._kickoff_position(p)
                    p.vel = (0.0, 0.0)
                    p.override = None
            taker.pos = (52.5 - self.attack_dir(side) * 0.5, 34.0)
        if initial:
            self.emit("kickoff", team=side, player=taker.id)
        self._start_restart("kickoff", side, (52.5, 34.0), taker, pause=pause)

    def _kickoff_position(self, p: PState) -> ph.Vec:
        code, bx, by = self.formations[p.side][p.slot]
        ax = 4.0 if code == "GK" else min(bx * 0.45 + 4, 48.0)
        return self.to_att(p.side, (ax, by))

    def _kickoff_taker(self, side: str) -> PState:
        forwards = [p for p in self.on_pitch[side] if p.code in ("ST", "AM", "CM")]
        return forwards[-1] if forwards else self.on_pitch[side][-1]

    def _pause(self, kind: str) -> float:
        """Seconds of dead ball before a restart is taken."""
        lo, hi = RESTART_PAUSE[kind]
        return self.rng.uniform(lo, hi)

    def _start_restart(self, kind: str, side: str, spot: ph.Vec, taker: PState | None = None,
                       pause: float = 3.0, reason: str | None = None) -> None:
        self.flight = None
        self.loose = None
        self.carrier = None
        self.carry_target = None
        self.carry_start = None
        spot = (max(0.0, min(PITCH_LENGTH, spot[0])), max(0.0, min(PITCH_WIDTH, spot[1])))
        self.ball = spot
        self._check_subs()
        if taker is None:
            if kind in ("goal_kick", "keeper"):
                taker = self.on_pitch[side][0]
            else:
                outfield = [p for p in self.on_pitch[side] if p.slot != 0]
                taker = min(outfield, key=lambda p: ph.dist(p.pos, spot))
        taker.override = spot
        taker.override_until = self.t + pause + 1.0
        if self.possession != side:
            self._set_possession(side, taker, reason or kind)
        self.restart = Restart(kind, side, spot, taker, self.t + pause)
        if kind == "corner":
            self.set_piece_until = self.t + pause + 6.0

    def _take_restart(self) -> None:
        r = self.restart
        assert r is not None
        self.restart = None
        r.taker.pos = r.spot
        r.taker.vel = (0.0, 0.0)
        r.taker.override = None
        self.force_cross = r.kind == "corner"
        self._gain_ball(r.taker, reason=None, decide_in=0.3 if r.kind == "kickoff" else 0.6)

    def _set_possession(self, side: str, player: PState | None, reason: str) -> None:
        if self.possession == side:
            return
        prev = self.possession
        self.possession = side
        if prev is not None:
            self.emit("possession_change", team=side, player=player.id if player else None, reason=reason,
                      at=_pt(player.pos if player else self.ball))
            self.transition_until = self.t + 4.0

    def _gain_ball(self, p: PState, reason: str | None, decide_in: float | None = None) -> None:
        if reason is not None:
            self._set_possession(p.side, p, reason)
        else:
            self.possession = p.side
        self.loose = None
        self.carrier = p
        self.carry_target = None
        self.carry_start = (p.pos, self.t)
        self.spell_start = self.t
        self.pressed = set()
        self.ball = p.pos
        p.override = None
        tempo = self.styles[p.side].tempo * self._mods(p.side).tempo
        if decide_in is None:
            decide_in = tempo * self.rng.uniform(1.5, 3.2)
            if self._pressure(p) > 0.5:
                decide_in *= 0.5
        self.next_decision = self.t + decide_in

    # ------------------------------------------------------------------
    # decisions

    def _decide(self) -> None:
        c = self.carrier
        assert c is not None
        side = c.side
        opp = other(side)
        style = self.styles[side]
        mods = self._mods(side)
        cp = self.to_att(side, c.pos)
        opp_att = [self.to_att(side, o.pos) for o in self.on_pitch[opp]]
        pressure = self._pressure(c)
        energy_factor = 0.85 + 0.15 * c.energy
        passing = c.player.passing * energy_factor
        risk = style.risk + mods.risk
        offside_line = self.offside_line(side)

        options: list[tuple[float, str, object]] = []

        # Shot
        d_goal = math.hypot(105.0 - cp[0], 34.0 - cp[1])
        header = self._is_header(c)
        if not self.force_cross and d_goal < 34 and cp[0] > 70:
            bodies = self._bodies_in_way(cp, opp_att)
            q = ph.shot_quality(d_goal, ph.goal_angle(cp), pressure, header) * 0.8 ** bodies
            fin = 0.75 + 0.5 * c.player.finishing / 100
            util = q * fin * style.shoot_bias * (1 + 0.15 * self.confidence[side]) * (1.25 if header else 1.0)
            util -= 0.3 * KEEP
            options.append((util, "shot", (q, header, bodies)))

        # Passes
        for m in self.on_pitch[side]:
            if m is c:
                continue
            mp = self.to_att(side, m.pos)
            if m.slot == 0 and (pressure < 0.4 or cp[0] > 40):
                continue
            lead = (min(103.0, mp[0] + 1.5), mp[1])
            d = ph.dist(cp, lead)
            if d < 4 or d > 55:
                continue
            lane = self._lane_gap(cp, lead, opp_att)
            space = min(ph.dist(o, lead) for o in opp_att)
            cross = cp[0] > 78 and (cp[1] < 16 or cp[1] > 52) and mp[0] > 86 and 18 < mp[1] < 50
            s = self._pass_success(d, lane, space, pressure, passing, cross)
            value = ph.position_value(lead)
            mid = ph.lerp(cp, lead, 0.5)
            loss = ph.position_value((105.0 - mid[0], 68.0 - mid[1]))
            if lead[0] > offside_line + 0.5 and lead[0] > cp[0]:
                continue
            util = s * (value + KEEP) - (1 - s) * (loss + KEEP) * (1.0 - 0.5 * risk)
            util += style.directness * 0.002 * max(0.0, lead[0] - cp[0]) / 10
            if self.force_cross:
                util = value if cross or mp[0] > 85 else -1.0
            options.append((util, "pass", (m, s, cross)))

        # Carries: forward, and forward-left / forward-right
        if not self.force_cross:
            for ang in (-0.7, 0.0, 0.7):
                tx = max(1.0, min(104.0, cp[0] + 7 * math.cos(ang)))
                ty = max(1.0, min(67.0, cp[1] + 7 * math.sin(ang)))
                tgt = (tx, ty)
                blockers = sum(1 for o in opp_att if ph.point_segment(o, cp, tgt)[0] < 3.0)
                drib = c.player.dribbling * energy_factor
                s = max(0.15, min(0.95, 0.92 - 0.45 * pressure - 0.15 * blockers + 0.15 * (drib - 65) / 35))
                loss = ph.position_value((105.0 - cp[0], 68.0 - cp[1]))
                util = s * (ph.position_value(tgt) + KEEP) - (1 - s) * (loss + KEEP) * (1.0 - 0.5 * risk)
                options.append((util, "carry", (tgt, s)))

        # Clearance: hoof it when pinned deep under pressure.
        if not self.force_cross and cp[0] < 28 and pressure > 0.5:
            options.append((0.25 * KEEP, "clearance", None))

        self.force_cross = False
        if not options:
            self.next_decision = self.t + 0.5
            return

        tau = 0.004 + 0.008 * (1.0 - passing / 100)
        best = max(u for u, _k, _d in options)
        weights = [math.exp((u - best) / tau) for u, _k, _d in options]
        util, kind, data = self.rng.choices(options, weights=weights)[0]

        if kind == "shot":
            q, hdr, bodies = data  # type: ignore[misc]
            self._shoot(c, q, hdr, pressure, bodies)
        elif kind == "clearance":
            self._clear(c, pressure)
        elif kind == "pass":
            m, s, cross = data  # type: ignore[misc]
            self._pass(c, m, s, cross, pressure)
        else:
            tgt, _s = data  # type: ignore[misc]
            self.carry_target = self.to_att(side, tgt)
            tempo = style.tempo * mods.tempo
            self.next_decision = self.t + tempo * self.rng.uniform(0.8, 1.6)

    def _pass_success(self, d: float, lane: float, space: float, pressure: float, passing: float, cross: bool) -> float:
        lane_open = max(0.0, min(1.0, (lane - 0.5) / 2.5))
        recv_space = max(0.0, min(1.0, (space - 1.0) / 3.0))
        s = (0.99 - 0.004 * d - 0.18 * pressure - 0.35 * (1 - lane_open) - 0.12 * (1 - recv_space)
             + 0.10 * (passing - 65) / 35)
        if cross:
            s -= 0.2
        return max(0.05, min(0.98, s))

    @staticmethod
    def _lane_gap(a: ph.Vec, b: ph.Vec, opps: list[ph.Vec]) -> float:
        """Closest an opponent stands to the passing lane, ignoring the first 2 m (that is pressure)."""
        length = max(ph.dist(a, b), 0.1)
        best = 99.0
        for o in opps:
            d, f = ph.point_segment(o, a, b)
            if f * length > 2.0 and d < best:
                best = d
        return best

    @staticmethod
    def _bodies_in_way(shooter: ph.Vec, opp_att: list[ph.Vec]) -> int:
        """Outfield opponents standing between the shooter and the goal mouth."""
        n = 0
        for o in opp_att[1:]:
            if o[0] <= shooter[0]:
                continue
            d, f = ph.point_segment(o, shooter, (105.0, 34.0))
            if 0 < f < 1 and d < 1.0 + 2.5 * f:
                n += 1
        return n

    def _is_header(self, c: PState) -> bool:
        lp = self.last_pass
        return bool(lp and lp["cross"] and lp["receiver"] == c.id and self.t - lp["t_end"] < 1.5)

    # ------------------------------------------------------------------
    # actions

    def _emit_carry(self, c: PState) -> None:
        if self.carry_start is None:
            return
        start, t0 = self.carry_start
        d = ph.dist(start, c.pos)
        if d >= 3.0:
            self.emit("carry", team=c.side, player=c.id, **{"from": _pt(start)}, to=_pt(c.pos),
                      distance_m=_r(d), duration_s=_r(self.t - t0))
        self.carry_start = None

    def _pass(self, c: PState, m: PState, s: float, cross: bool, pressure: float) -> None:
        self._emit_carry(c)
        side = c.side
        start = c.pos
        mp = self.to_att(side, m.pos)
        lead = self.to_att(side, (min(103.0, mp[0] + 1.5), mp[1]))
        d = ph.dist(start, lead)
        speed = ph.pass_speed(d) * self.rng.uniform(0.9, 1.1)
        if cross:
            speed = max(speed, 19.0)
        receiver: PState | None
        if self.rng.random() < s:
            outcome, end, receiver = "complete", lead, m
        else:
            best_o, best_d, best_f = None, 1e9, 0.0
            for o in self.on_pitch[other(side)]:
                dd, f = ph.point_segment(o.pos, start, lead)
                if f * d > 2.0 and dd < best_d:
                    best_o, best_d, best_f = o, dd, f
            if best_o is not None and best_d < 3.5 and self.rng.random() < 0.75:
                outcome, receiver = "intercepted", best_o
                end = ph.lerp(start, lead, max(0.15, best_f))
            else:
                outcome, receiver = "incomplete", None
                err = 4.0 + d * 0.15
                end = _just_off_pitch((lead[0] + self.rng.gauss(0, err), lead[1] + self.rng.gauss(0, err)))
        travel = ph.dist(start, end)
        self.emit(
            "pass", team=side, player=c.id, **{"from": _pt(start)}, to=_pt(end), outcome=outcome,
            receiver=m.id, intercepted_by=receiver.id if outcome == "intercepted" else None,
            pressure=_r(pressure), distance_m=_r(d), ball_speed_kmh=_r(speed * 3.6), cross=cross,
        )
        self.flight = Flight("pass", start, end, self.t, max(0.2, travel / speed), outcome, c, receiver, cross)
        self.carrier = None
        self.carry_target = None
        if receiver is not None:
            receiver.override = end
            receiver.override_until = self.t + self.flight.duration + 0.5

    def _shoot(self, c: PState, q: float, header: bool, pressure: float, bodies: int) -> None:
        self._emit_carry(c)
        side = c.side
        cp = self.to_att(side, c.pos)
        gk = self.on_pitch[other(side)][0]
        fin = 0.75 + 0.35 * c.player.finishing / 100
        keeper = 1.2 - 0.3 * gk.player.goalkeeping / 100
        p_goal = max(0.005, min(0.9, q * fin * keeper))
        p_block = 0.0 if header else min(0.7, 0.08 + 0.25 * pressure + 0.15 * bodies)
        r = self.rng.random()
        if r < p_goal:
            outcome = "goal"
        elif r < p_goal + (1 - p_goal) * p_block:
            outcome = "blocked"
        elif self.rng.random() < 0.42:
            outcome = "saved"
        else:
            outcome = "off_target"

        if outcome in ("goal", "saved"):
            end_att = (105.0, self.rng.uniform(GOAL_POSTS[0] + 0.3, GOAL_POSTS[1] - 0.3))
            if outcome == "saved":
                end_att = (104.0, end_att[1])
        elif outcome == "blocked":
            f = self.rng.uniform(1.5, 4.0) / max(1.0, math.hypot(105 - cp[0], 34 - cp[1]))
            end_att = ph.lerp(cp, (105.0, 34.0), min(0.6, f))
        else:
            wide = self.rng.choice([-1, 1]) * self.rng.uniform(0.3, 5.0)
            y = GOAL_POSTS[1] + wide if wide > 0 else GOAL_POSTS[0] + wide
            end_att = (106.0, y)
        end = self.to_att(side, end_att)

        power = self.rng.random() * (0.6 + 0.4 * c.player.finishing / 100)
        speed = self.rng.uniform(9, 15) if header else 19 + 13 * power
        dist = math.hypot(105 - cp[0], 34 - cp[1])
        assist = None
        lp = self.last_pass
        if lp and lp["receiver"] == c.id and self.t - lp["t_end"] < 8:
            assist = lp["player"]
        situation = "set_piece" if self.t < self.set_piece_until else "open_play"
        if self.t < self.transition_until and self.possession == side:
            situation = "counter" if situation == "open_play" else situation
        self.emit(
            "shot", team=side, player=c.id, **{"from": _pt(c.pos)}, to=_pt(end), outcome=outcome,
            shot_speed_kmh=_r(speed * 3.6), distance_m=_r(dist), angle_deg=_r(math.degrees(ph.goal_angle(cp))),
            body_part="head" if header else "foot", situation=situation, pressure=_r(pressure),
            key_pass_by=assist,
        )
        self.flight = Flight("shot", c.pos, end, self.t, max(0.15, ph.dist(c.pos, end) / speed), outcome, c)
        self.carrier = None
        self.carry_target = None
        self._bump_confidence(side, 0.08)

    def _clear(self, c: PState, pressure: float) -> None:
        self._emit_carry(c)
        side = c.side
        cp = self.to_att(side, c.pos)
        end_att = (self.rng.uniform(55, 85), cp[1] + self.rng.gauss(0, 18))
        end = _just_off_pitch(self.to_att(side, end_att))
        d = ph.dist(c.pos, end)
        speed = self.rng.uniform(22, 28)
        self.emit("clearance", team=side, player=c.id, **{"from": _pt(c.pos)}, to=_pt(end),
                  pressure=_r(pressure), distance_m=_r(d), ball_speed_kmh=_r(speed * 3.6))
        self.flight = Flight("clearance", c.pos, end, self.t, d / speed, "loose", c)
        self.carrier = None
        self.carry_target = None

    def _loose_ball(self, spot: ph.Vec, last_touch: str) -> None:
        """Nobody controls the ball: it goes out, or the nearest player picks it up."""
        x, y = spot
        if (y < 0 or y > PITCH_WIDTH) or (min(y, PITCH_WIDTH - y) < 4 and self.rng.random() < 0.4):
            out = (max(1.0, min(104.0, x)), 0.0 if y < 34 else PITCH_WIDTH)
            self.emit("out", team=last_touch, player=None, at=_pt(out), restart="throw_in")
            self._start_restart("throw_in", other(last_touch), out, pause=self._pause("throw_in"), reason="out")
            return
        spot = (max(0.5, min(PITCH_LENGTH - 0.5, x)), y)
        self._drop_ball(spot, last_touch)

    def _drop_ball(self, spot: ph.Vec, last_touch: str, reserved: PState | None = None,
                   reason: str | None = None) -> None:
        self.carrier = None
        self.carry_target = None
        self.ball = spot
        self.loose = Loose(spot, last_touch, self.t, reserved, reason)
        if reserved is not None:
            reserved.override = spot
            reserved.override_until = self.t + 3.0

    def _collect_loose(self) -> None:
        lb = self.loose
        assert lb is not None
        waited = self.t - lb.since
        if lb.reserved is not None and waited < 3.0:
            if ph.dist(lb.reserved.pos, lb.spot) <= 1.2:
                self._gain_ball(lb.reserved, reason=lb.reason)
            return
        players = [p for s in SIDES for p in self.on_pitch[s]]
        nearest = min(players, key=lambda p: ph.dist(p.pos, lb.spot))
        if ph.dist(nearest.pos, lb.spot) <= 1.0 or waited > 8.0:
            self._gain_ball(nearest, reason="loose_ball")

    def _loose_chasers(self) -> set[str]:
        """While the ball is loose, the nearest player from each side goes for it."""
        lb = self.loose
        if lb is None or (lb.reserved is not None and self.t - lb.since < 1.0):
            return set()
        out = set()
        for s in SIDES:
            out.add(min(self.on_pitch[s], key=lambda p: ph.dist(p.pos, lb.spot)).id)
        return out

    def _advance_flight(self) -> None:
        f = self.flight
        assert f is not None
        prog = (self.t - f.t0) / f.duration
        if prog < 1.0:
            self.ball = ph.lerp(f.start, f.end, prog)
            return
        self.ball = f.end
        self.flight = None
        if f.kind == "pass":
            self._resolve_pass(f)
        elif f.kind == "clearance":
            self._loose_ball(f.end, f.passer.side)
        else:
            self._resolve_shot(f)

    def _resolve_pass(self, f: Flight) -> None:
        side = f.passer.side
        if f.outcome == "complete" and f.receiver is not None:
            self.last_pass = {"player": f.passer.id, "receiver": f.receiver.id, "cross": f.cross, "t_end": self.t}
            end_att = self.to_att(side, f.end)
            self._bump_confidence(side, 0.02 if end_att[0] > 70 else 0.005)
            self._receive(f.receiver, f.end, side, reason=None)
            return
        self._bump_confidence(side, -0.03)
        if f.outcome == "intercepted" and f.receiver is not None:
            if f.cross and self.rng.random() < 0.4:
                end_att = self.to_att(side, f.end)
                spot = self.to_att(side, (105.0, 0.0 if end_att[1] < 34 else PITCH_WIDTH))
                self.emit("clearance", team=f.receiver.side, player=f.receiver.id, **{"from": _pt(f.end)},
                          to=_pt(spot), pressure=0.0, distance_m=_r(ph.dist(f.end, spot)), ball_speed_kmh=None)
                self.emit("out", team=f.receiver.side, player=f.receiver.id, at=_pt(spot), restart="corner")
                self._start_restart("corner", side, spot, pause=self._pause("corner"), reason="out")
                return
            self.emit("interception", team=f.receiver.side, player=f.receiver.id, at=_pt(f.end),
                      from_player=f.passer.id)
            self._receive(f.receiver, f.end, side, reason="interception")
            return
        # Misplaced pass: out of play or a loose ball.
        x, y = f.end
        if y < 0 or y > PITCH_WIDTH:
            spot = (max(1.0, min(104.0, x)), 0.0 if y < 0 else PITCH_WIDTH)
            self.emit("out", team=side, player=f.passer.id, at=_pt(spot), restart="throw_in")
            self._start_restart("throw_in", other(side), spot, pause=self._pause("throw_in"), reason="out")
            return
        if x < 0 or x > PITCH_LENGTH:
            att_x = self.to_att(side, (x, y))[0]
            if att_x > PITCH_LENGTH:
                spot = self.to_att(other(side), (5.5, 34.0 + self.rng.choice([-9.0, 9.0])))
                self.emit("out", team=side, player=f.passer.id, at=_pt((x, y)), restart="goal_kick")
                self._start_restart("goal_kick", other(side), spot, pause=self._pause("goal_kick"), reason="out")
            else:
                corner_y = 0.0 if y < 34 else PITCH_WIDTH
                spot = (0.0 if x < 0 else PITCH_LENGTH, corner_y)
                self.emit("out", team=side, player=f.passer.id, at=_pt((x, y)), restart="corner")
                self._start_restart("corner", other(side), spot, pause=self._pause("corner"), reason="out")
            return
        self._loose_ball(f.end, side)

    def _receive(self, p: PState, spot: ph.Vec, last_touch: str, reason: str | None) -> None:
        """Ball arrives for a player: take it now if they are there, otherwise they have first claim."""
        if ph.dist(p.pos, spot) <= 1.2:
            self._gain_ball(p, reason=reason)
        else:
            self._drop_ball(spot, last_touch, reserved=p, reason=reason)

    def _resolve_shot(self, f: Flight) -> None:
        side = f.passer.side
        opp = other(side)
        gk = self.on_pitch[opp][0]
        if f.outcome == "goal":
            self.score[side] += 1
            assist = self.last_pass["player"] if self.last_pass and self.last_pass["receiver"] == f.passer.id \
                and self.t - self.last_pass["t_end"] < 8 else None
            self.emit("goal", team=side, player=f.passer.id, assist=assist,
                      score={"HOME": self.score["HOME"], "AWAY": self.score["AWAY"]})
            self._bump_confidence(side, 0.25)
            self._bump_confidence(opp, -0.15)
            self.last_pass = None
            self._kickoff(opp, teleport=False, pause=self._pause("kickoff"))
            return
        self.last_pass = None
        if f.outcome == "saved":
            self.emit("save", team=opp, player=gk.id, shooter=f.passer.id, at=_pt(f.end))
            if self.rng.random() < 0.35:
                end_att = self.to_att(side, f.end)
                spot = self.to_att(side, (105.0, 0.0 if end_att[1] < 34 else PITCH_WIDTH))
                self.emit("out", team=opp, player=gk.id, at=_pt(f.end), restart="corner")
                self._start_restart("corner", side, spot, pause=self._pause("corner"), reason="out")
            else:
                self._start_restart("keeper", opp, self.to_att(opp, (6.0, 34.0)), taker=gk,
                                    pause=self._pause("keeper"), reason="save")
        elif f.outcome == "off_target":
            spot = self.to_att(opp, (5.5, 34.0 + self.rng.choice([-9.0, 9.0])))
            self.emit("out", team=side, player=f.passer.id, at=_pt(f.end), restart="goal_kick")
            self._start_restart("goal_kick", opp, spot, pause=self._pause("goal_kick"), reason="out")
        else:  # blocked
            defenders = self.on_pitch[opp][1:]
            blocker = min(defenders, key=lambda p: ph.dist(p.pos, f.end))
            self.emit("block", team=opp, player=blocker.id, shooter=f.passer.id, at=_pt(f.end))
            if self.rng.random() < 0.35:
                end_att = self.to_att(side, f.end)
                spot = self.to_att(side, (105.0, 0.0 if end_att[1] < 34 else PITCH_WIDTH))
                self.emit("out", team=opp, player=blocker.id, at=_pt(f.end), restart="corner")
                self._start_restart("corner", side, spot, pause=self._pause("corner"), reason="out")
                return
            self._drop_ball(f.end, opp)

    def _defend(self) -> None:
        c = self.carrier
        assert c is not None
        opps = self.on_pitch[other(c.side)]
        nearest = min(opps, key=lambda o: ph.dist(o.pos, c.pos))
        d = ph.dist(nearest.pos, c.pos)
        if d < 2.0 and not self.pressed:
            self.pressed.add(nearest.id)
            self.emit("pressure", team=nearest.side, player=nearest.id, on=c.id, at=_pt(c.pos),
                      intensity=_r(self._pressure(c)))
            self.next_decision = min(self.next_decision, self.t + self.rng.uniform(0.6, 1.4))
        if d > 1.6 or self.t < self.tackle_ready_at or self.t < nearest.beaten_until or nearest.slot == 0:
            return
        style = self.styles[nearest.side]
        rate = 0.045 * (nearest.player.defending / 70) * (1.0 + 0.3 * (style.press_trigger > 12))
        if self.rng.random() >= rate:
            return
        self.tackle_ready_at = self.t + 0.8
        mods = self._mods(nearest.side)
        p_foul = 0.22 + (0.05 if mods.press > 0 else 0.0)
        p_win = max(0.25, min(0.8, 0.52 + (nearest.player.defending - c.player.dribbling) / 120))
        r = self.rng.random()
        if r < p_foul:
            card = "yellow" if self.rng.random() < 0.14 else None
            self.emit("foul", team=nearest.side, player=nearest.id, on=c.id, at=_pt(c.pos), card=card)
            self._emit_carry(c)
            self._start_restart("free_kick", c.side, c.pos, taker=c, pause=self._pause("free_kick"))
        elif r < p_foul + (1 - p_foul) * p_win:
            self._emit_carry(c)
            self.emit("tackle", team=nearest.side, player=nearest.id, on=c.id, at=_pt(c.pos), outcome="won")
            self._bump_confidence(c.side, -0.03)
            c.beaten_until = self.t + 1.0
            if self.rng.random() < 0.35:
                spot = (c.pos[0] + self.rng.gauss(0, 4), c.pos[1] + self.rng.gauss(0, 4))
                self.carrier = None
                self._loose_ball(spot, nearest.side)
            else:
                self._gain_ball(nearest, reason="tackle")
        else:
            self.emit("tackle", team=nearest.side, player=nearest.id, on=c.id, at=_pt(c.pos), outcome="lost")
            nearest.beaten_until = self.t + 1.5

    # ------------------------------------------------------------------
    # movement

    def _move_players(self) -> None:
        ball = self.ball
        k = min(1.0, DT / 1.0)
        self.ball_seen = (self.ball_seen[0] + (ball[0] - self.ball_seen[0]) * k,
                          self.ball_seen[1] + (ball[1] - self.ball_seen[1]) * k)
        for side in SIDES:
            style = self.styles[side]
            mods = self._mods(side)
            in_poss = self.possession == side
            ball_att = self.to_att(side, self.ball_seen)
            line = self.offside_line(side) - 0.5 if in_poss else PITCH_LENGTH
            presser = cover = None
            if not in_poss and self.possession is not None and self.restart is None:
                ranked = sorted((p for p in self.on_pitch[side] if p.slot != 0 and self.t >= p.beaten_until),
                                key=lambda p: ph.dist(p.pos, ball))
                trigger = style.press_trigger + mods.press * 0.5
                own_third = ball_att[0] < 35
                if ranked and (ph.dist(ranked[0].pos, ball) < trigger or own_third):
                    presser = ranked[0]
                    if len(ranked) > 1:
                        cover = ranked[1]
            marks = self._marking(side, ball_att, presser, cover) if not in_poss and self.restart is None else {}
            chasers = self._loose_chasers()
            for p in self.on_pitch[side]:
                top = ph.top_speed(p.player.pace, p.energy)
                if p is self.carrier and self.flight is None:
                    if self.carry_target is not None:
                        target, speed = self.carry_target, 0.68 * top
                    else:
                        target, speed = p.pos, 0.2 * top
                elif p.override is not None and self.t < p.override_until:
                    target, speed = p.override, top
                elif p.id in chasers:
                    target, speed = ball, 0.95 * top
                elif self.restart is not None and self.restart.kind == "kickoff":
                    target = self._kickoff_position(p)
                    speed = top * (0.2 if ph.dist(p.pos, target) < 3 else 0.45)
                elif p is presser:
                    target, speed = ball, 0.92 * top
                elif p is cover:
                    gx = 0.0 if self.attack_dir(side) > 0 else PITCH_LENGTH
                    target = ph.lerp(ball, (gx, 34.0), 0.15)
                    speed = 0.8 * top
                else:
                    if self.restart is not None and self.restart.kind == "corner" and p.slot != 0:
                        target_att = self._corner_target(p, side)
                    else:
                        _code, bx, by = self.formations[side][p.slot]
                        target_att = shape_target(p.code, (bx, by), ball_att, in_poss, style, mods)
                    if self.t >= p.run_offset_until:
                        spread = 4.0 if in_poss else 2.0
                        p.run_offset = (self.rng.gauss(0, spread), self.rng.gauss(0, spread))
                        p.run_offset_until = self.t + self.rng.uniform(5, 12)
                    if p.id in marks:
                        mx, my = marks[p.id]
                        target_att = (0.5 * target_att[0] + 0.5 * mx, 0.5 * target_att[1] + 0.5 * my)
                    elif p.slot != 0:
                        target_att = (min(line, target_att[0] + p.run_offset[0]), target_att[1] + p.run_offset[1])
                    target = self.to_att(side, target_att)
                    d = ph.dist(p.pos, target)
                    frac = 0.1 if d < 2 else 0.18 if d < 6 else 0.33 if d < 12 else 0.6
                    if self.t < self.transition_until:
                        frac = min(0.95, frac * 1.25)
                    speed = top * frac
                target = (max(-1.0, min(PITCH_LENGTH + 1, target[0])), max(-1.0, min(PITCH_WIDTH + 1, target[1])))
                old = p.pos
                p.pos, p.vel = ph.step(p.pos, p.vel, target, speed, DT)
                p.pos = _just_off_pitch(p.pos)
                moved = ph.dist(old, p.pos)
                p.distance += moved
                v = moved / DT
                if v > p.top_speed:
                    p.top_speed = v
                if v > 25 / 3.6:
                    p.sprint_distance += moved
                drain = moved * 0.33 / 10500 * (1.5 - p.player.stamina / 100) / 0.8
                p.energy = max(0.3, p.energy - drain + (0.00002 if v < 2 else 0.0))

    def _marking(self, side: str, ball_att: ph.Vec, presser: PState | None, cover: PState | None) -> dict[str, ph.Vec]:
        """Defenders pick up nearby attackers once the ball is in their half (attacking frame of `side`)."""
        if ball_att[0] > 55:
            return {}
        attackers = [self.to_att(side, a.pos) for a in self.on_pitch[other(side)]
                     if a.slot != 0 and a is not self.carrier]
        out: dict[str, ph.Vec] = {}
        taken: set[int] = set()
        style, mods = self.styles[side], self._mods(side)
        for p in self.on_pitch[side]:
            if p.slot == 0 or p is presser or p is cover or p.player.group == "FWD":
                continue
            _code, bx, by = self.formations[side][p.slot]
            home = shape_target(p.code, (bx, by), ball_att, False, style, mods)
            best, best_d = -1, 12.0
            for i, a in enumerate(attackers):
                if i in taken:
                    continue
                d = ph.dist(home, a)
                if d < best_d:
                    best, best_d = i, d
            if best >= 0:
                taken.add(best)
                ax, ay = attackers[best]
                gx, gy = 0.0 - ax, 34.0 - ay
                n = math.hypot(gx, gy) or 1.0
                out[p.id] = (ax + gx / n * 2.5, ay + gy / n * 2.5)
        return out

    def _corner_target(self, p: PState, side: str) -> ph.Vec:
        """Attackers crowd the box at corners; defenders mark it."""
        in_poss = self.possession == side
        _code, bx, by = self.formations[side][p.slot]
        if in_poss:
            if p.code in ("CB",) or p.player.position in ("ST", "AM", "CM", "LW", "RW", "DM"):
                return (self.rng.uniform(92, 101), self.rng.uniform(26, 42))
            return shape_target(p.code, (bx, by), (95.0, 34.0), True, self.styles[side], Mods())
        if p.code in ("CB", "LB", "RB", "DM", "CM", "ST"):
            return (self.rng.uniform(2, 11), self.rng.uniform(26, 42))
        return shape_target(p.code, (bx, by), (5.0, 34.0), False, self.styles[side], Mods())

    # ------------------------------------------------------------------
    # substitutions and periods

    def _check_subs(self) -> None:
        clock = self.clock_seconds()
        for side in SIDES:
            n = self.subs_made[side]
            if n >= 3 or clock < self.sub_times[side][n] or not self.bench[side]:
                continue
            busy = {self.carrier.id if self.carrier else None}
            candidates = [p for p in self.on_pitch[side] if p.slot != 0 and p.id not in busy]
            if not candidates:
                continue
            out = min(candidates, key=lambda p: p.energy + self.rng.uniform(0, 0.05))
            same = [b for b in self.bench[side] if b.group == out.player.group]
            pool = same or [b for b in self.bench[side] if b.group != "GK"]
            if not pool:
                continue
            new = pool[0]
            self.bench[side].remove(new)
            touchline = (52.5, 0.0)
            ps = PState(new, side, out.slot, touchline)
            self.on_pitch[side][out.slot] = ps
            self.all_players[ps.id] = ps
            self.subs_made[side] += 1
            self.emit("substitution", team=side, player_in=new.id, player_out=out.id, slot=out.slot)
            self.lineups.append(self._lineup_snapshot())

    def _check_period_end(self) -> None:
        if self.flight is not None:
            return
        if self.t - self.period_start < HALF_SECONDS + self.stoppage[self.period]:
            return
        self.restart = None
        self._emit_carry(self.carrier) if self.carrier else None
        if self.period == 1:
            self.emit("half_time", score=dict(self.score))
            self.period = 2
            self.period_start = self.t
            self.possession = None
            self.confidence = {s: c * 0.5 for s, c in self.confidence.items()}
            for s in SIDES:
                for p in self.on_pitch[s]:
                    p.energy = min(1.0, p.energy + 0.08)
            kicker = other(self.first_kickoff)
            self.emit("kickoff", team=kicker, player=self._kickoff_taker(kicker).id)
            self._kickoff(kicker)
        else:
            self.emit("full_time", score=dict(self.score))
            self.carrier = None
            self.finished = True

    # ------------------------------------------------------------------
    # summaries

    def player_physical(self) -> dict[str, dict]:
        out = {}
        for ps in self.all_players.values():
            out[ps.id] = {
                "distance_m": round(ps.distance),
                "sprint_distance_m": round(ps.sprint_distance),
                "top_speed_kmh": _r(ps.top_speed * 3.6),
                "energy_end": round(ps.energy, 2),
            }
        return out
