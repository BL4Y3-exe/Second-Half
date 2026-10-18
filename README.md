# Second Half

A live AI studio team for a synthetic football match. A simulator plays a
made-up match, a stats engine turns it into numbers, and a team of agents
decides what matters, explains it, fact-checks itself and puts graphics on
screen, tuned to each viewer (Analyst, Casual fan, Player focus, Favourite
club, any language).

Built for the Microsoft *Inside the Game* developer hackathon. All clubs,
players and matches are fictional.

> **Status:** early build. Done: match simulator, stats engine, live feed
> server and the browser pitch view. Next: agents, overlays as plugins,
> Telestrator, viewer modes.

## Quickstart

You need Python 3.11+ and, for the browser view, Node.js 20.19+ (or 22.12+).
On Windows, use `py` where these commands say `python`.

```bash
python -m pip install -r requirements.txt

# build the web app once (and again after pulling changes to web/)
cd web
npm install
npm run build
cd ..

# start the server, then open http://127.0.0.1:8000
python -m api
```

The page starts Harbourside Athletic v Kingsmere Rovers (seed 9: a
second-half comeback with a stoppage-time winner) at 10x speed. Pick
other clubs, a seed and a speed at the top and press **Kick off**. You can
also link straight to a match: `http://127.0.0.1:8000/?seed=12&speed=20`.

**Working on the web app?** Run `python -m api` in one terminal and
`npm run dev` inside `web/` in another, then open http://localhost:5173.
Changes reload instantly.

## Command line

No extra packages needed for these.

```bash
# full match in a few seconds: score and team stats
python -m simulator summary --seed 9

# watch the events scroll by, 20x faster than real time
python -m simulator live --seed 9 --speed 20 --pretty

# raw JSON lines, the format the rest of the system consumes
python -m simulator live --seed 9 --speed 50

# save a whole match (events + player positions) to JSON
python -m simulator export --seed 9

# run the stats engine over a match: xG, field tilt, PPDA, key-moment triggers
python -m stats --seed 9
```

Clubs: `harbourside`, `kingsmere`, `ashford`, `northgate` (`--home`,
`--away`). The same seed always replays the same match.

## How it fits together

```
simulator  ->  stats engine  ->  live feed (FastAPI, Server-Sent Events)  ->  web app (React)
 positions      xG, speeds,        one match per (clubs, seed, speed),        pitch, score bug,
 + events       momentum,          shared by every viewer                     stats, match feed
                triggers
```

### Simulator (`simulator/`)

- Four fictional clubs, each with 16 players (pace, passing, finishing,
  stamina, pressing, defending, dribbling, goalkeeping) and a style: high
  press, possession or counter-attack.
- Ticks every 0.1 s: all 22 players and the ball have real positions, so
  speeds, distances and Telestrator drawings come from actual geometry.
- Players weigh passing, carrying, shooting and clearing against the risk
  of losing the ball. Defenders press, cover, mark and get goal-side;
  attackers stay onside. Loose balls are chased, not teleported.
- Events: pass, carry, shot, goal, save, block, tackle, interception,
  clearance, foul (with cards), pressure, out of play (throw-in, goal kick,
  corner), possession change, substitution, kickoff, half time, full time.
- Fatigue, confidence, the score and the clock change behaviour.
- Averages over many matches: about 2.2 goals, 15 shots, 76% pass
  completion, 30 throw-ins, 6 corners, 35 fouls and 11 km per outfield player.

### Stats engine (`stats/`)

Plain code, no AI: every number an agent says later is checked against it.

- **xG** for every shot from distance, angle, body part, situation and
  pressure. Over many simulated matches xG tracks actual goals.
- **Pass difficulty** (0 to 1) from distance, pressure on the passer, how
  open the lane was and how much space the receiver had.
- **Speeds and running** from positions: top speed, distance, sprints.
- **Control vs Chaos** index (0 to 100) from pass completion, possession
  length, turnovers and duels over the last 5 minutes.
- **Momentum** (-100 to 100), field tilt, PPDA and high turnovers.
- **Triggers** with a priority for the Spotter agent: goal, big chance,
  momentum swing, shot over 100 km/h, killer pass, fastest sprint of the
  match, 10 km covered.

### Live feed (`api/`)

`GET /api/live?home=harbourside&away=kingsmere&seed=9&speed=10` streams
Server-Sent Events: `meta` (team sheets), `frame` (positions, about 12 a
second), `event` (with computed stats attached), `trigger`, `stats` (a
snapshot every second) and `end`. Viewers of the same match share one
running match.

The data formats are documented in [docs/schema.md](docs/schema.md).

## Development

```bash
python -m pip install -r requirements-dev.txt
ruff check .
python -m pytest -q
cd web && npm run typecheck
```

CI runs lint, tests and the web build on every push
(`.github/workflows/ci.yml`).

## Licence

MIT. See [LICENSE](LICENSE).
