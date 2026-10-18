"""python -m stats [--seed N | path/to/match.json]: analyse a match and print the numbers."""

from __future__ import annotations

import argparse
import json

from simulator import simulate_match

from .analyse import analyse_match
from .state import SIDES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m stats", description="Second Half stats engine")
    parser.add_argument("match", nargs="?", help="saved match JSON (default: simulate one)")
    parser.add_argument("--seed", type=int, default=9)
    parser.add_argument("--home", default="harbourside")
    parser.add_argument("--away", default="kingsmere")
    parser.add_argument("--json", action="store_true", help="print the full snapshot as JSON")
    args = parser.parse_args(argv)

    if args.match:
        with open(args.match, encoding="utf-8") as fh:
            match = json.load(fh)
    else:
        match = simulate_match(args.home, args.away, args.seed, frame_step=0.2)
    state = analyse_match(match)

    if args.json:
        print(json.dumps({"snapshot": state.snapshot(), "triggers": state.triggers}, indent=2))
        return 0

    h, a = (state.team_stats(s) for s in SIDES)
    names = [state.teams[s]["name"] for s in SIDES]
    print(f"\n  {names[0]}  {h['goals']} - {a['goals']}  {names[1]}\n")
    rows = [("xG", "xg"), ("Shots", "shots"), ("Possession %", "possession_pct"),
            ("Pass completion %", "pass_completion_pct"), ("Final-third passes", "final_third_passes"),
            ("Field tilt %", "field_tilt_pct"), ("PPDA", "ppda"), ("High turnovers", "high_turnovers"),
            ("Distance (km)", "distance_km"), ("Corners", "corners")]
    for label, key in rows:
        print(f"  {str(h[key]):>8}  {label:^20}  {str(a[key]):<8}")
    print("\n  Triggers the Spotter agent will see:")
    for tr in state.triggers:
        print(f"   {tr['clock']}  {tr['kind']:<15} {tr['label']}")
    fastest = max((state.player_stats(p) for p in state.players), key=lambda p: p["top_speed_kmh"])
    furthest = max((state.player_stats(p) for p in state.players), key=lambda p: p["distance_m"])
    print(f"\n  Fastest: {fastest['name']} {fastest['top_speed_kmh']} km/h. "
          f"Most running: {furthest['name']} {furthest['distance_m'] / 1000:.1f} km.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
