"""python -m agents --seed 9: run a whole match through the studio team and print what it put on screen."""

from __future__ import annotations

import argparse
import asyncio

from simulator import MatchEngine, build_team
from stats import MatchState

from .models import MockModel
from .orchestrator import Orchestrator


async def run(args: argparse.Namespace) -> None:
    engine = MatchEngine(build_team(args.home, "HOME"), build_team(args.away, "AWAY"), seed=args.seed,
                         frame_step=0.5)
    meta = {"teams": {s: t.to_dict() for s, t in engine.teams.items()}}
    state = MatchState(meta)
    printed: list[tuple[str, dict]] = []
    orch = Orchestrator(state, lambda kind, data: printed.append((kind, data)), speed=args.speed,
                        model=MockModel(seed=args.seed, mistake_rate=args.mistakes), languages=(args.lang,))

    def show() -> None:
        for kind, d in printed:
            if kind == "overlay":
                print(f"\n  {d['clock']}  [{d['plugin']}] {d['headline']}")
                print(f"          {d['text'][args.lang][args.mode]}")
            elif kind == "trace" and args.trace:
                mark = {"rejected": "x", "fallback": "!", "skipped": "-"}.get(d["status"], " ")
                print(f"     {mark} {d['agent']:<12} {d['action']:<12} {d['summary']}")
        printed.clear()

    for tick in engine.run():
        triggers = []
        if tick.frame is not None:
            triggers += state.apply_frame(tick.frame)
        for ev in tick.events:
            _enriched, trs = state.apply_event(ev)
            triggers += trs
        orch.observe(tick.events, triggers, tick.t)
        await orch.drain()
        show()
    orch.flush(state.t)
    await orch.drain()
    show()
    s = orch.stats
    print(f"\n  {s['moments']} moments, {s['caught']} wrong numbers caught by the Fact-checker, "
          f"{s['fallbacks']} fallbacks, {s['dropped']} dropped to avoid clutter.\n")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m agents", description="Run the Second Half studio team")
    parser.add_argument("--seed", type=int, default=9)
    parser.add_argument("--home", default="harbourside")
    parser.add_argument("--away", default="kingsmere")
    parser.add_argument("--speed", type=float, default=10.0, help="viewing speed the Director schedules for")
    parser.add_argument("--mode", default="analyst", choices=["analyst", "casual", "player"])
    parser.add_argument("--lang", default="en", choices=["en", "es"])
    parser.add_argument("--mistakes", type=float, default=0.2, help="how often the mock Storyteller slips")
    parser.add_argument("--trace", action="store_true", help="show every agent handoff")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
