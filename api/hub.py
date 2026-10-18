"""Runs live matches and fans their updates out to every viewer.

One engine + stats state per match key (clubs, seed, speed). Viewers that
join late get the team sheets and the current state first, then the live
stream. Agents will subscribe here too.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field

from simulator import MatchEngine, build_team
from stats import MatchState

FRAME_RATE = 12.0  # position frames per wall-clock second sent to viewers
STATS_EVERY_S = 1.0  # wall-clock seconds between stats snapshots
KEEP_FINISHED_S = 60.0  # keep a finished match around briefly for late viewers


@dataclass(frozen=True)
class MatchKey:
    home: str
    away: str
    seed: int
    speed: float

    @property
    def id(self) -> str:
        return f"{self.home}-{self.away}-{self.seed}-x{self.speed:g}"


@dataclass
class LiveMatch:
    key: MatchKey
    engine: MatchEngine
    state: MatchState
    meta: dict
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    task: asyncio.Task | None = None
    last_frame: dict | None = None
    finished: bool = False

    def hello(self) -> list[tuple[str, dict]]:
        """What a new viewer needs before the live stream."""
        out = [("meta", self.meta), ("stats", self.state.snapshot())]
        if self.last_frame is not None:
            out.append(("frame", self.last_frame))
        out += [("event", e) for e in self.state.events[-12:]]
        return out

    def publish(self, kind: str, data: dict) -> None:
        for q in list(self.subscribers):
            if q.qsize() > 2000:  # a stuck viewer should not grow memory without bound
                continue
            q.put_nowait((kind, data))


class MatchHub:
    def __init__(self) -> None:
        self.matches: dict[MatchKey, LiveMatch] = {}

    def get_or_start(self, key: MatchKey) -> LiveMatch:
        live = self.matches.get(key)
        if live is not None and (not live.finished or live.subscribers):
            return live
        home, away = build_team(key.home, "HOME"), build_team(key.away, "AWAY")
        engine = MatchEngine(home, away, seed=key.seed, frame_step=0.1)
        meta = {
            "match_id": key.id,
            "seed": key.seed,
            "speed": key.speed,
            "pitch": [105.0, 68.0],
            "teams": {"HOME": home.to_dict(), "AWAY": away.to_dict()},
        }
        state = MatchState(meta)
        live = LiveMatch(key, engine, state, meta)
        live.task = asyncio.create_task(self._run(live))
        self.matches[key] = live
        return live

    async def _run(self, live: LiveMatch) -> None:
        key = live.key
        started = time.perf_counter()
        frame_every = max(0.1, key.speed / FRAME_RATE)  # match seconds between frames sent
        next_frame_t = 0.0
        next_stats = started
        for tick in live.engine.run():
            # Pace match time against the wall clock.
            wait = started + tick.t / key.speed - time.perf_counter()
            if wait > 0:
                await asyncio.sleep(wait)
            if tick.frame is not None:
                for tr in live.state.apply_frame(tick.frame):
                    live.publish("trigger", tr)
                live.last_frame = tick.frame
                if tick.t >= next_frame_t:
                    live.publish("frame", tick.frame)
                    next_frame_t = tick.t + frame_every
            for ev in tick.events:
                enriched, triggers = live.state.apply_event(ev)
                live.publish("event", enriched)
                for tr in triggers:
                    live.publish("trigger", tr)
            now = time.perf_counter()
            if now >= next_stats or live.engine.finished:
                live.publish("stats", live.state.snapshot())
                next_stats = now + STATS_EVERY_S
            if wait <= 0:
                await asyncio.sleep(0)  # let viewers drain when running flat out
        live.finished = True
        live.publish("end", {"score": live.state.score})
        await asyncio.sleep(KEEP_FINISHED_S)
        if not live.subscribers and self.matches.get(key) is live:
            del self.matches[key]

    def subscribe(self, live: LiveMatch) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        for item in live.hello():
            q.put_nowait(item)
        if live.finished:
            q.put_nowait(("end", {"score": live.state.score}))
        live.subscribers.add(q)
        return q

    def unsubscribe(self, live: LiveMatch, q: asyncio.Queue) -> None:
        live.subscribers.discard(q)
        if not live.subscribers and live.task is not None and not live.finished:
            # Nobody is watching: stop the match rather than burn CPU.
            live.task.cancel()
            with contextlib.suppress(KeyError):
                if self.matches[live.key] is live:
                    del self.matches[live.key]
