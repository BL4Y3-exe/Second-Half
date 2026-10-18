# Data schema

Everything in Second Half talks in three JSON shapes: **match events**,
**overlay items** and **viewer profiles**. This page documents what the
simulator produces today (match events, frames and saved matches); overlay
items and viewer profiles are added as those parts are built.

Coordinates are metres on a 105 x 68 pitch with the origin at a corner flag.
`x` runs along the length (0 to 105) and `y` across the width (0 to 68).
The home team attacks towards `x = 105` in the first half and towards
`x = 0` in the second.

## Match event

Every event has these fields:

| Field | Type | Meaning |
|---|---|---|
| `id` | string | `e-00042`, unique within a match, in order |
| `t` | number | seconds since kickoff, continuous across both halves (0.1 s resolution) |
| `period` | 1 or 2 | half |
| `clock` | string | match clock as `MM:SS`; the second half starts at `45:00`, stoppage time keeps counting (`47:12`) |
| `type` | string | one of the types below |
| `team` | `HOME` or `AWAY` | the team that did it (missing on `half_time`, `full_time`) |
| `player` | string | player id such as `h-09` (home) or `a-10` (away) |

Type-specific fields:

| Type | Extra fields |
|---|---|
| `kickoff` | |
| `pass` | `from`, `to` ([x, y]), `outcome` (`complete`, `intercepted`, `incomplete`), `receiver` (intended target), `intercepted_by`, `pressure` (0 to 1 on the passer), `distance_m` (to the intended target), `ball_speed_kmh`, `cross` (bool) |
| `carry` | `from`, `to`, `distance_m`, `duration_s`. Emitted when a player who ran at least 3 m with the ball releases it |
| `shot` | `from`, `to`, `outcome` (`goal`, `saved`, `blocked`, `off_target`), `shot_speed_kmh`, `distance_m` (to the goal centre), `angle_deg` (goal mouth angle), `body_part` (`foot`, `head`), `situation` (`open_play`, `counter`, `set_piece`), `pressure`, `key_pass_by` |
| `goal` | `assist` (player id or null), `score` ({HOME, AWAY} after the goal) |
| `save` | `shooter`, `at` |
| `block` | `shooter`, `at` |
| `pressure` | `on` (the carrier), `at`, `intensity` (0 to 1). A defender closing the carrier to within 2 m, once per possession spell |
| `tackle` | `on`, `at`, `outcome` (`won`, `lost`) |
| `interception` | `at`, `from_player` |
| `clearance` | `from`, `to`, `pressure`, `distance_m`, `ball_speed_kmh` |
| `foul` | `on`, `at`, `card` (`yellow` or null) |
| `out` | `at`, `restart` (`throw_in`, `goal_kick`, `corner`). `team` is the side that put it out |
| `possession_change` | `reason` (`interception`, `tackle`, `loose_ball`, `out`, `save`, `kickoff`, `free_kick`, ...), `at` |
| `substitution` | `player_in`, `player_out`, `slot` (0 to 10, the position in the lineup) |
| `half_time`, `full_time` | `score` |

Example:

```json
{"id": "e-01042", "t": 2041.3, "period": 1, "clock": "34:01", "type": "pass",
 "team": "HOME", "player": "h-09", "from": [61.2, 30.5], "to": [84.0, 22.1],
 "outcome": "complete", "receiver": "h-11", "intercepted_by": null,
 "pressure": 0.7, "distance_m": 24.3, "ball_speed_kmh": 54.2, "cross": false}
```

## Frame

The simulator ticks every 0.1 s. A frame is a snapshot of all 22 players and the ball:

```json
{"t": 2041.5, "period": 1, "b": [62.0, 30.1], "p": [[5.1, 34.0], "... 22 pairs"], "o": "h-09"}
```

- `p` lists home slots 0 to 10, then away slots 0 to 10. Slot 0 is the goalkeeper.
- `o` is the id of the player on the ball, or null while the ball is travelling or dead.
- Which player is in which slot comes from `lineups` in a saved match (it changes only at substitutions).

## Computed stats on events (stats engine)

The stats engine adds a `stats` object to some events before they reach the
live feed:

| Event | `stats` fields |
|---|---|
| `pass` | `difficulty` (0 to 1), `difficulty_label` (`easy`, `medium`, `hard`, `very hard`), `lane_gap_m`, `receiver_space_m`, `progress_m` |
| `shot`, `goal` | `xg` |
| `carry` | `progress_m` |

## Trigger (stats engine to Spotter agent)

```json
{"id": "tr-0007", "t": 1580.4, "clock": "26:20", "kind": "shot_speed", "priority": 2,
 "team": "HOME", "player": "h-09", "value": 104.0,
 "label": "Ade Delacroix strikes it at 104 km/h", "source_events": ["e-00812"]}
```

Kinds: `goal`, `big_chance` (xG 0.3+ and not scored), `momentum_swing`,
`shot_speed` (100 km/h+), `killer_pass` (hard pass into the final 25 m),
`sprint_speed` (new fastest sprint of the match, 32 km/h+, after 5 minutes),
`distance_10k` (first three players past 10 km). Priority 1 must be shown,
2 is worth showing, 3 is filler.

## Saved match (`python -m simulator export`)

```json
{
  "meta": {"schema_version": 1, "seed": 42, "pitch": [105, 68], "tick_s": 0.1, "frame_step_s": 0.5,
           "first_kickoff": "HOME", "home_attacks_right_in_first_half": true,
           "teams": {"HOME": {"name": "...", "short": "HAR", "colors": ["#1f6feb", "#ffffff"],
                              "style": "high_press", "formation": "4-3-3", "players": ["..."]},
                     "AWAY": {"...": "..."}}},
  "summary": {"score": {"HOME": 2, "AWAY": 1}, "teams": {"...": "..."}, "players": {"h-09": {"distance_m": 10450, "top_speed_kmh": 33.1}}},
  "lineups": [{"t": 0.0, "HOME": ["h-01", "..."], "AWAY": ["a-01", "..."]}],
  "events": ["..."],
  "frames": ["..."]
}
```

Each player in `teams.*.players` has `id`, `name`, `number`, `position` and
attributes from 20 to 97: `pace`, `passing`, `finishing`, `stamina`,
`pressing`, `defending`, `dribbling`, `goalkeeping`. The first 11 are the
starters in slot order; the rest are the bench.
