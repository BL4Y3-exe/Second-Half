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

## Overlay item (Director to browser)

One graphic the Director scheduled. Sent as the `overlay` SSE event.

```json
{"id": "ov-0010", "moment_id": "m-010", "kind": "goal", "clock": "42:58",
 "show_at": 2580.3, "duration_s": 7.0, "priority": 1,
 "plugin": "goal-card", "slot": "lower-third", "team": "HOME", "player": "h-08",
 "headline": "GOAL · Kofi Holloway",
 "data": {"player": "Kofi Holloway", "xg": 0.66, "distance_m": 4, "shot_speed_kmh": 79,
          "score_home": 1, "score_away": 0},
 "telestrator": {"arrows": [{"kind": "shot", "from": [101.4, 35.2], "to": [105.0, 33.6], "t": 2578.2}],
                 "zones": [{"kind": "circle", "center": [101.4, 35.2], "r": 2.5, "label": "0.66 xG"}],
                 "highlight": ["h-08"], "window": [2576.2, 2580.2]},
 "facts_checked": true, "fallback": false, "source_events": ["e-01389", "e-01388"],
 "story": "Kofi Holloway scores from 4 m at 79 km/h. The chance was worth 0.66 xG; HAR 1-0 KMR.",
 "text": {"en": {"analyst": "...", "casual": "GOAL! Kofi Holloway scores for Harbourside Athletic! HAR 1-0 KMR.",
                 "player": "Kofi Holloway today: 1 goal from 2 shots, 1.18 xG."},
          "es": {"analyst": "...", "casual": "...", "player": "..."}}}
```

- `show_at` is in match seconds: the browser puts the item up when the
  match clock reaches it and keeps it for `duration_s` seconds of viewing
  time. A lower `priority` number takes the slot from a higher one.
- `slot`: `lower-third`, `corner`, `pitch` (pinned to a player),
  `full-pitch` or `full-screen`.
- `telestrator` is null when the moment has no geometry. Arrow `kind` is
  `pass`, `carry` or `shot`; `t` is when it happened, and `window` is the
  stretch of play the browser replays under the drawing.
- `fallback` is true when the story failed fact-checking twice and a plain
  `stat-card` went out instead (`data.line` holds its text).
- `text[lang][mode]` is the Persona agent's version for each viewer mode
  (`analyst`, `casual`, `player`) and language.

## Agent trace step

One handoff between agents. Sent as the `trace` SSE event.

```json
{"id": "st-00042", "t": 2578.2, "clock": "42:58", "moment_id": "m-010",
 "agent": "fact_checker", "action": "rejected",
 "summary": "says 6 m, but match data has 4 m (distance_m)", "status": "rejected", "ms": 0.0,
 "detail": {"problems": ["says 6 m, but match data has 4 m (distance_m)"], "checked": ["6 m", "79 km/h"]}}
```

`agent` is one of `spotter`, `analyst`, `storyteller`, `fact_checker`,
`director`, `persona`, `recap`. `status` is `ok`, `rejected`, `fallback` or
`skipped` (a moment the Spotter passed over or the Director held back; its
`moment_id` is then the trigger id).

## Graphics plugin manifest (`plugins/<id>/manifest.json`)

```json
{"id": "goal-card", "name": "Goal card", "version": "1.0.0", "author": "Second Half", "builtin": true,
 "slot": "lower-third", "needs": ["scorer", "assist", "xg", "score"], "default_duration_s": 7,
 "description": "Lower third for a goal, with the chance quality."}
```

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
