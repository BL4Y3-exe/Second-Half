"""python -m mcp_server --seed 9 --minute 60: an MCP server over stdio for one simulated match.

Plays the match (with the agent team, in mock mode) up to the minute given, then
answers questions about it. To ask about live matches instead, run `python -m api`
and point your MCP client at http://127.0.0.1:8000/mcp.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field

from agents import MockModel, Orchestrator
from simulator import CLUBS, MatchEngine, build_team
from stats import MatchState

from .server import build_server, summary


@dataclass
class PlayedMatch:
    match_id: str
    state: MatchState
    overlays: list[dict] = field(default_factory=list)


class OneMatch:
    def __init__(self, match: PlayedMatch):
        self.match = match

    def matches(self) -> list[dict]:
        return [summary(self.match.match_id, self.match.state)]

    def lookup(self, match_id: str | None) -> PlayedMatch:
        if match_id not in (None, "", self.match.match_id):
            raise ValueError(f"no match {match_id!r}; this server has {self.match.match_id!r}")
        return self.match


def minutes(clock: str) -> float:
    mm, ss = clock.split(":")
    return int(mm) + int(ss) / 60


async def play(home: str, away: str, seed: int, minute: float | None) -> PlayedMatch:
    """Plays the match through the stats engine and the agent team, up to `minute` (or full time)."""
    engine = MatchEngine(build_team(home, "HOME"), build_team(away, "AWAY"), seed=seed, frame_step=0.5)
    state = MatchState({"teams": {s: t.to_dict() for s, t in engine.teams.items()}})
    orch = Orchestrator(state, lambda kind, data: None, model=MockModel(seed=seed))
    for tick in engine.run():
        triggers = state.apply_frame(tick.frame) if tick.frame is not None else []
        for ev in tick.events:
            triggers += state.apply_event(ev)[1]
        orch.observe(tick.events, triggers, tick.t)
        await orch.drain()
        if minute is not None and tick.period >= (1 if minute < 45 else 2) and minutes(state.clock) >= minute:
            break
    else:
        orch.flush(state.t)
        await orch.drain()
    return PlayedMatch(f"{home}-{away}-{seed}", state, orch.overlays)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m mcp_server", description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--home", default="harbourside", choices=sorted(CLUBS))
    parser.add_argument("--away", default="kingsmere", choices=sorted(CLUBS))
    parser.add_argument("--minute", type=float, default=None, help="stop the match here (default: full time)")
    args = parser.parse_args()
    match = asyncio.run(play(args.home, args.away, args.seed, args.minute))
    build_server(OneMatch(match)).run("stdio")


if __name__ == "__main__":
    main()
