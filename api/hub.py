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

from agents import Orchestrator
from agents.models import load_model
from mcp_server.server import summary
from simulator import MatchEngine, build_team
from stats import MatchState

FRAME_RATE = 12.0  # position frames per wall-clock second sent to viewers
STATS_EVERY_S = 1.0  # wall-clock seconds between stats snapshots
KEEP_FINISHED_S = 60.0  # keep a finished match around briefly for late viewers
FINISH_RECAP_S = 45.0  # longest the full-time whistle waits for the agent team to finish
# How long an unwatched match keeps playing. A viewer whose stream drops (a proxy timeout, a flaky
# connection) reconnects within seconds and should find the same match still running.
RECONNECT_GRACE_S = 20.0


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
    orchestrator: Orchestrator | None = None
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    task: asyncio.Task | None = None
    agents_task: asyncio.Task | None = None
    last_frame: dict | None = None
    finished: bool = False
    started_at: float = field(default_factory=time.time)

    @property
    def overlays(self) -> list[dict]:
        return self.orchestrator.overlays if self.orchestrator is not None else []

    def hello(self) -> list[tuple[str, dict]]:
        """What a new viewer needs before the live stream."""
        out = [("meta", self.meta), ("stats", self.state.snapshot())]
        if self.last_frame is not None:
            out.append(("frame", self.last_frame))
        out += [("event", e) for e in self.state.events[-12:]]
        if self.orchestrator is not None:
            out += [("trace", s) for s in self.orchestrator.trace[-40:]]
            out += [("overlay", o) for o in self.orchestrator.overlays[-6:]]
        return out

    def publish(self, kind: str, data: dict) -> None:
        for q in list(self.subscribers):
            if q.qsize() > 2000:  # a stuck viewer should not grow memory without bound
                continue
            q.put_nowait((kind, data))


class MatchHub:
    def __init__(self, grace_s: float = RECONNECT_GRACE_S) -> None:
        self.matches: dict[MatchKey, LiveMatch] = {}
        self.grace_s = grace_s
        self._stops: set[asyncio.Task] = set()

    def get_or_start(self, key: MatchKey) -> LiveMatch:
        live = self.matches.get(key)
        if live is not None and (not live.finished or live.subscribers):
            return live
        home, away = build_team(key.home, "HOME"), build_team(key.away, "AWAY")
        engine = MatchEngine(home, away, seed=key.seed, frame_step=0.1)
        model = load_model(key.seed)
        meta = {
            "match_id": key.id,
            "seed": key.seed,
            "speed": key.speed,
            "pitch": [105.0, 68.0],
            "teams": {"HOME": home.to_dict(), "AWAY": away.to_dict()},
            "model": model.name,
            "languages": ["en", "es"],
        }
        state = MatchState(meta)
        live = LiveMatch(key, engine, state, meta)
        live.orchestrator = Orchestrator(state, live.publish, speed=key.speed, model=model, seed=key.seed,
                                         languages=tuple(meta["languages"]))
        live.agents_task = asyncio.create_task(live.orchestrator.run())
        live.task = asyncio.create_task(self._run(live))
        self.matches[key] = live
        return live

    async def _run(self, live: LiveMatch) -> None:
        key = live.key
        started = time.perf_counter()
        frame_every = max(0.1, key.speed / FRAME_RATE)  # match seconds between frames sent
        next_frame_t = 0.0
        next_stats = started
        orch = live.orchestrator
        for tick in live.engine.run():
            # Pace match time against the wall clock.
            wait = started + tick.t / key.speed - time.perf_counter()
            if wait > 0:
                await asyncio.sleep(wait)
            triggers: list[dict] = []
            if tick.frame is not None:
                triggers += live.state.apply_frame(tick.frame)
                live.last_frame = tick.frame
                if tick.t >= next_frame_t:
                    live.publish("frame", tick.frame)
                    next_frame_t = tick.t + frame_every
            for ev in tick.events:
                enriched, trs = live.state.apply_event(ev)
                live.publish("event", enriched)
                triggers += trs
            for tr in triggers:
                live.publish("trigger", tr)
            if orch is not None:
                orch.observe(tick.events, triggers, tick.t)
            now = time.perf_counter()
            if now >= next_stats or live.engine.finished:
                live.publish("stats", live.state.snapshot())
                next_stats = now + STATS_EVERY_S
            if wait <= 0:
                await asyncio.sleep(0)  # let viewers drain when running flat out
        if orch is not None:
            orch.flush(live.state.t)
            with contextlib.suppress(TimeoutError):  # let the team finish the full-time recap before "end"
                await asyncio.wait_for(orch.queue.join(), timeout=FINISH_RECAP_S)
        live.finished = True
        live.publish("end", {"score": live.state.score})
        await asyncio.sleep(KEEP_FINISHED_S)
        if live.agents_task is not None:
            live.agents_task.cancel()
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
        if live.subscribers or live.task is None or live.finished:
            return
        if self.grace_s <= 0:
            self._stop_if_unwatched(live)
            return
        stop = asyncio.create_task(self._stop_later(live))
        self._stops.add(stop)
        stop.add_done_callback(self._stops.discard)

    async def _stop_later(self, live: LiveMatch) -> None:
        await asyncio.sleep(self.grace_s)
        self._stop_if_unwatched(live)

    def _stop_if_unwatched(self, live: LiveMatch) -> None:
        """Nobody is watching: stop the match rather than burn CPU."""
        if live.subscribers or live.task is None or live.finished:
            return
        live.task.cancel()
        if live.agents_task is not None:
            live.agents_task.cancel()
        with contextlib.suppress(KeyError):
            if self.matches[live.key] is live:
                del self.matches[live.key]


class HubSource:
    """Lets the MCP server answer about the matches in the hub."""

    def __init__(self, hub: MatchHub):
        self.hub = hub

    def _live(self) -> list[LiveMatch]:
        return sorted(self.hub.matches.values(), key=lambda m: m.started_at)

    def matches(self) -> list[dict]:
        return [summary(m.key.id, m.state) for m in self._live()]

    def lookup(self, match_id: str | None) -> LiveMatch:
        live = self._live()
        if not live:
            raise ValueError("no match is running; open the web app (or GET /api/live) to start one")
        if not match_id:
            return live[-1]
        for m in live:
            if m.key.id == match_id:
                return m
        raise ValueError(f"no match {match_id!r}; running: {', '.join(m.key.id for m in live)}")
