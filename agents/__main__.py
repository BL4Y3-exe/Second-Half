"""python -m agents --seed 9: run a whole match through the studio team and print what it put on screen.

Uses Microsoft Foundry when FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL are set (or in .env), the
scripted mock otherwise. `--model foundry --until 30 --trace` is a quick check that Foundry works."""

from __future__ import annotations

import argparse
import asyncio

from simulator import MatchEngine, build_team
from stats import MatchState

from .models import MockModel, load_model
from .orchestrator import Orchestrator
from .settings import load_env


async def run(args: argparse.Namespace) -> None:
    engine = MatchEngine(build_team(args.home, "HOME"), build_team(args.away, "AWAY"), seed=args.seed,
                         frame_step=0.5)
    meta = {"teams": {s: t.to_dict() for s, t in engine.teams.items()}}
    state = MatchState(meta)
    printed: list[tuple[str, dict]] = []
    model = load_model(args.seed, args.model)
    if isinstance(model, MockModel):
        model.mistake_rate = args.mistakes
    print(f"\n  model: {model.name}")
    orch = Orchestrator(state, lambda kind, data: printed.append((kind, data)), speed=args.speed,
                        model=model, languages=(args.lang,), plant_slips=args.plant)

    def show() -> None:
        for kind, d in printed:
            if kind == "overlay":
                print(f"\n  {d['clock']}  [{d['plugin']}] {d['headline']}")
                print(f"          {d['text'][args.lang][args.mode]}")
            elif kind == "trace" and args.trace:
                mark = {"rejected": "x", "fallback": "!", "skipped": "-"}.get(d["status"], " ")
                ms = f"  ({d['ms'] / 1000:.1f} s)" if d["ms"] >= 100 else ""
                print(f"     {mark} {d['agent']:<12} {d['action']:<12} {d['summary']}{ms}")
        printed.clear()

    for tick in engine.run():
        if args.until and tick.t >= args.until * 60 and not state.finished:
            break
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
    planted = f" ({s['planted']} planted by the demo switch)" if s["planted"] else ""
    print(f"\n  {s['moments']} moments, {s['caught']} wrong numbers caught by the Fact-checker{planted}, "
          f"{s['fallbacks']} fallbacks, {s['dropped']} dropped to avoid clutter.\n")


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(prog="python -m agents", description="Run the Second Half studio team")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--home", default="harbourside")
    parser.add_argument("--away", default="kingsmere")
    parser.add_argument("--speed", type=float, default=8.0, help="viewing speed the Director schedules for")
    parser.add_argument("--mode", default="analyst", choices=["analyst", "casual", "player"])
    parser.add_argument("--lang", default="en", choices=["en", "es"])
    parser.add_argument("--model", default="auto", choices=["auto", "mock", "foundry"],
                        help="auto: Foundry when FOUNDRY_* settings are present, else the scripted mock")
    parser.add_argument("--until", type=int, default=0, help="stop after this many minutes of match time")
    parser.add_argument("--mistakes", type=float, default=0.2, help="how often the mock Storyteller slips")
    parser.add_argument("--trace", action="store_true", help="show every agent handoff")
    parser.add_argument("--plant", action="store_true",
                        help="demo switch: plant a wrong number in the first story and each goal for the Fact-checker")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
