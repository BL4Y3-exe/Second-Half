"""Command line: python -m simulator {export,live,summary} ..."""

from __future__ import annotations

import argparse
import json
import sys
import time

from .engine import MatchEngine
from .export import save_match, simulate_match
from .teams import CLUBS, build_team


def _print_summary(match: dict) -> None:
    s = match["summary"]
    h, a = s["teams"]["HOME"], s["teams"]["AWAY"]
    print(f"\n  {h['name']}  {h['goals']} - {a['goals']}  {a['name']}   (seed {match['meta']['seed']})\n")
    rows = [
        ("Possession %", "possession_pct"), ("Shots", "shots"), ("On target", "shots_on_target"),
        ("Passes", "passes"), ("Pass completion %", "pass_completion_pct"), ("Carries", "carries"),
        ("Tackles (won)", None), ("Interceptions", "interceptions"), ("Pressures", "pressures"),
        ("Fouls", "fouls"), ("Yellow cards", "yellow_cards"),
    ]
    for label, key in rows:
        if key is None:
            hv, av = f"{h['tackles']} ({h['tackles_won']})", f"{a['tackles']} ({a['tackles_won']})"
        else:
            hv, av = h[key], a[key]
        print(f"  {str(hv):>10}  {label:^20}  {str(av):<10}")
    print()
    for ev in match["events"]:
        if ev["type"] == "goal":
            team = match["meta"]["teams"][ev["team"]]
            names = {p["id"]: p["name"] for p in team["players"]}
            assist = f" (assist {names.get(ev['assist'], ev['assist'])})" if ev.get("assist") else ""
            print(f"  {ev['clock']}  GOAL {team['short']}  {names[ev['player']]}{assist}")
    print()


def _quiet_main(argv: list[str] | None = None) -> int:
    try:
        return main(argv)
    except BrokenPipeError:  # e.g. piped into `head`
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m simulator", description="Second Half synthetic match simulator")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--seed", type=int, default=42, help="same seed, same match (default 42)")
        p.add_argument("--home", default="harbourside", choices=sorted(CLUBS))
        p.add_argument("--away", default="kingsmere", choices=sorted(CLUBS))

    p_exp = sub.add_parser("export", help="simulate a whole match and save it as JSON")
    common(p_exp)
    p_exp.add_argument("--out", help="output path (default data/matches/<home>-<away>-<seed>.json)")
    p_exp.add_argument("--frame-step", type=float, default=0.5, help="seconds between saved position frames")

    p_sum = sub.add_parser("summary", help="simulate a match and print the score and stats")
    common(p_sum)

    p_live = sub.add_parser("live", help="stream events as JSON lines in (sped-up) real time")
    common(p_live)
    p_live.add_argument("--speed", type=float, default=10.0, help="1 = real time, 10 = ten times faster")
    p_live.add_argument("--frames", action="store_true", help="also print position frames")
    p_live.add_argument("--pretty", action="store_true", help="human-readable lines instead of JSON")

    args = parser.parse_args(argv)
    if args.home == args.away:
        parser.error("--home and --away must be different clubs")

    if args.cmd == "export":
        match = simulate_match(args.home, args.away, args.seed, args.frame_step)
        out = args.out or f"data/matches/{args.home}-{args.away}-{args.seed}.json"
        path = save_match(match, out)
        _print_summary(match)
        print(f"  Saved {len(match['events'])} events and {len(match['frames'])} frames to {path}")
        return 0

    if args.cmd == "summary":
        _print_summary(simulate_match(args.home, args.away, args.seed, frame_step=60.0))
        return 0

    engine = MatchEngine(build_team(args.home, "HOME"), build_team(args.away, "AWAY"), seed=args.seed)
    names = {p.id: p.name for t in engine.teams.values() for p in t.players}
    shorts = {side: t.short for side, t in engine.teams.items()}
    started = time.perf_counter()
    try:
        for tick in engine.run():
            wait = started + tick.t / args.speed - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
            for ev in tick.events:
                if args.pretty:
                    if ev["type"] in ("pressure", "carry") and not args.frames:
                        continue  # keep the readable feed short
                    print(_pretty(ev, names, shorts))
                else:
                    print(json.dumps(ev))
            if args.frames and tick.frame is not None:
                print(json.dumps({"type": "frame", **tick.frame}))
            sys.stdout.flush()
    except (KeyboardInterrupt, BrokenPipeError):
        pass
    return 0


def _pretty(ev: dict, names: dict[str, str], shorts: dict[str, str]) -> str:
    who = names.get(ev.get("player") or "", "")
    typ = ev["type"]
    detail = ""
    if typ == "pass":
        detail = f"-> {names[ev['receiver']]}  ({ev['outcome']}, {ev['distance_m']:.0f} m)"
    elif typ == "shot":
        detail = f"{ev['outcome'].replace('_', ' ')}, {ev['distance_m']:.0f} m, {ev['shot_speed_kmh']:.0f} km/h"
    elif typ in ("goal", "half_time", "full_time"):
        score = ev["score"]
        detail = f"{shorts['HOME']} {score['HOME']} - {score['AWAY']} {shorts['AWAY']}"
    elif typ == "substitution":
        who = names[ev["player_in"]]
        detail = f"on for {names[ev['player_out']]}"
    elif typ in ("tackle", "foul"):
        detail = f"on {names[ev['on']]}" + (f", {ev['outcome']}" if ev.get("outcome") else "")
        detail += ", yellow card" if ev.get("card") else ""
    elif typ == "possession_change":
        detail = ev["reason"].replace("_", " ")
    elif typ == "out":
        detail = ev["restart"].replace("_", " ")
    team = shorts.get(ev.get("team", ""), "")
    label = "GOAL!" if typ == "goal" else typ.replace("_", " ")
    return f"{ev['clock']}  {label:<17} {team:<4} {who:<22} {detail}"


if __name__ == "__main__":
    raise SystemExit(_quiet_main())
