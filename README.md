# Second Half

A live AI studio team for a synthetic football match. A simulator plays a
made-up match, a stats engine turns it into numbers, and a team of agents
decides what matters, explains it, fact-checks itself and puts graphics on
screen, tuned to each viewer (Analyst, Casual fan, Player focus, Favourite
club, any language).

Built for the Microsoft *Inside the Game* developer hackathon. All clubs,
players and matches are fictional.

> **Status:** in progress. Done: match simulator, stats engine, live feed,
> browser pitch view, the agent team with graphics plugins (on Microsoft
> Foundry or a built-in mock model), the Telestrator, viewer modes and the
> agent trace, and the MCP server. Next: the Azure deployment.

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
other clubs, a seed and a speed at the top and press **Kick off**.

While the match plays, the agent team puts graphics over the pitch: goal,
chance and pass cards, momentum swings, top-speed tags and half-time and
full-time recaps. Moments with a Telestrator drawing replay the move on the
pitch with the arrows drawn in as the ball travels. Above the pitch you can
switch the viewer mode (Analyst, Casual fan, Player focus), the language
(English, Español) and pick a favourite club. The **Agent trace** tab on the
right shows every handoff between the agents, including the wrong numbers
the Fact-checker caught.

**Split screen** (top right) shows the same live match to two viewers side
by side, each with their own mode, language and club, next to the agent
trace. By default it is an English-speaking analyst and a Spanish-speaking
casual Kingsmere fan. It is laid out for a 1920x1080 screen recording.

No Azure account or API key is needed: unless you set up Microsoft Foundry
(below), the agents run on a built-in mock model that writes from templates
and deliberately slips a wrong number into some first drafts (always
including the first goal's), so you can watch the Fact-checker catch it.

You can link straight to a set-up, which is handy for demos:
`http://127.0.0.1:8000/?seed=12&speed=20&mode=casual&lang=es&fav=HOME&tab=trace`,
or `http://127.0.0.1:8000/?view=split` for the split screen.

**Working on the web app?** Run `python -m api` in one terminal and
`npm run dev` inside `web/` in another, then open http://localhost:5173.
Changes reload instantly.

## Running the agents on Microsoft Foundry

The Storyteller, Persona and Recap agents can write with a real model
deployed in [Microsoft Foundry](https://ai.azure.com). Sign-in uses
Microsoft Entra ID, so there are no API keys to keep.

1. In the Foundry portal, create a project and deploy a model, for example
   `gpt-5.4-mini` (Global Standard). Creating the project in the portal
   gives you the **Foundry User** role, which is what the app needs.
2. Install the [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)
   and run `az login`.
3. Copy `.env.example` to `.env` and fill in the project endpoint (from the
   project's overview page) and the deployment name:

   ```bash
   FOUNDRY_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
   FOUNDRY_MODEL=gpt-5.4-mini
   ```

4. Check it works on the first half hour of a match, then start the server
   as usual:

   ```bash
   python -m agents --model foundry --until 30 --trace
   python -m api
   ```

The agent trace shows which model is writing (the chip next to its title).
Models from the gpt-5 family think before they answer; the app asks for
`low` effort by default. For the quickest lines set
`FOUNDRY_REASONING_EFFORT=minimal` (gpt-5, gpt-5-mini, gpt-5-nano) or
`none` (gpt-5.1 and later). For a model without reasoning, leave it empty
(`FOUNDRY_REASONING_EFFORT=`).

Live TV can't wait for a slow model, so every call has a 20-second limit.
If the model doesn't answer, the Storyteller's moment goes out as a plain
stat card, and a Persona or Recap version falls back to the scripted line
built from the same facts. Minor moments the team only reaches after 25
seconds are dropped. All of this shows up in the trace.

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

# run a match through the agent team and print what it put on screen
python -m agents --seed 9
python -m agents --seed 9 --trace              # every handoff, rejected drafts marked x
python -m agents --seed 9 --mode casual --lang es
python -m agents --model foundry --until 30    # on Microsoft Foundry (see above), first 30 minutes
```

Clubs: `harbourside`, `kingsmere`, `ashford`, `northgate` (`--home`,
`--away`). The same seed always replays the same match.

## How it fits together

```
simulator  ->  stats engine  ->  agent team  ->  live feed (FastAPI, SSE)  ->  web app (React)
 positions      xG, speeds,       Spotter ...      one match per (clubs,       pitch, graphics,
 + events       momentum,         Recap, with      seed, speed), shared        Telestrator, viewer
                triggers          match tools      by every viewer             modes, agent trace
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

### Agent team (`agents/`)

Seven agents work each key moment in turn:

| Agent | Job |
| --- | --- |
| Spotter | Watches the stats engine's triggers, merges ones that belong together (a shot and its goal) and holds back minor moments so the screen isn't cluttered. |
| Analyst | Looks up the facts with the match tools: the passage of play, xG, speeds, the player's and team's numbers. |
| Storyteller | Writes one or two sentences on why the moment matters, using only those facts. |
| Fact-checker | Plain code, no AI. Every number and player name in the draft must match match state. If not, it sends the draft back with the reason; after two failures (or if the model doesn't answer) a plain stat card goes out instead. |
| Director | Picks the graphics plugin and slot, builds the Telestrator drawing from real event positions, and schedules items so graphics never pile up. |
| Persona | Rewrites the approved story for each viewer mode and language, all at once; each version is fact-checked again, and one that fails falls back to a scripted line built from the facts. |
| Recap | Writes the half-time and full-time summaries with player ratings. |

The agents talk to a model through one small interface
(`agents/models.py`). With Foundry configured, the Storyteller, Persona and
Recap each run as a [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/)
agent on a shared Foundry chat client (`agents/foundry.py`); otherwise
they use the mock model. The other four agents are plain code. The
prompts are in `agents/prompts/`.

**Match tools (`mcp_server/`).** What the Analyst and Recap agents can ask
about the match: score, team and player stats, the sequence that led to an
event, trends, comparisons, top players and the graphics plugins
available. The MCP server below exposes the same tools to any MCP client.

**Graphics plugins (`plugins/`).** Every graphic is a plugin with a
manifest saying which stats it needs, which slot it uses (lower third,
corner, pitch, full screen) and how long it stays up. The Director chooses
from these; the browser draws them (`web/src/plugins/`).

Plugins from outside authors run in a sandbox: a locked-down iframe with
no access to the page and no network, which only receives the data it
asked for. `plugins/xg-race/` is an example from a made-up outside studio,
Touchline Labs: a chart of each team's running xG that the Director picks
for momentum swings. [docs/plugins.md](docs/plugins.md) explains how to
write one.

### Live feed (`api/`)

`GET /api/live?home=harbourside&away=kingsmere&seed=9&speed=10` streams
Server-Sent Events: `meta` (team sheets), `frame` (positions, about 12 a
second), `event` (with computed stats attached), `trigger`, `stats` (a
snapshot every second), `overlay` (a graphic the Director scheduled),
`trace` (one agent handoff) and `end`. Viewers of the same match share one
running match and one agent team.

The data formats are documented in [docs/schema.md](docs/schema.md).

### MCP server (`mcp_server/`)

The live server also speaks the [Model Context Protocol](https://modelcontextprotocol.io)
at `http://127.0.0.1:8000/mcp` (Streamable HTTP), so any MCP client
(GitHub Copilot in VS Code, Claude, a Foundry agent) can ask about the
match people are watching. It has 12 tools: `list_matches`, `get_score`,
`get_team_stats`, `get_player_stats`, `compare_players`, `top_players`,
`get_recent_events`, `get_sequence`, `get_trend`, `get_xg_race`, `get_on_screen` (what the
agent team has shown, with its fact-checked stories) and `list_plugins`.
Leave out `match_id` to ask about the match that started most recently.

**VS Code:** this repo includes `.vscode/mcp.json`, so with `python -m api`
running and a match open in the browser, start the `second-half` server
from the MCP view and ask Copilot Chat (agent mode) things like "who has
the highest xG so far?" or "how did the last goal come about?".

**Any other client:** point it at `http://127.0.0.1:8000/mcp`, or run a
replay over stdio without the web app (it plays the match to the minute
given, then answers about it):

```bash
python -m mcp_server --seed 9 --minute 60
```

When the server runs under a public host name (for example on Azure
Container Apps), list that name in `MCP_ALLOWED_HOSTS` (comma-separated).
Requests addressed to any other host are refused, which guards against DNS
rebinding.

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
