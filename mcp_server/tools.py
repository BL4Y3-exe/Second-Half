"""The tools agents use to look things up instead of guessing.

Each method returns plain JSON-ready data computed by the stats engine. The
agents call them in-process; `mcp_server.server` exposes the same tools over
MCP so any MCP client (GitHub Copilot, Claude, Foundry agents) can query a
live match.
"""

from __future__ import annotations

import json
from pathlib import Path

from stats import MatchState

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
SEQUENCE_TYPES = {"pass", "carry", "shot", "goal", "possession_change", "interception", "tackle"}
TREND_METRICS = ("xg", "possession_pct", "control_chaos", "momentum", "field_tilt")


def list_plugins() -> list[dict]:
    """Every installed graphics plugin's manifest."""
    out = []
    for manifest in sorted(PLUGINS_DIR.glob("*/manifest.json")):
        with manifest.open(encoding="utf-8") as fh:
            out.append(json.load(fh))
    return out


class MatchTools:
    def __init__(self, state: MatchState):
        self.state = state

    # --- the tool surface -------------------------------------------------

    def get_score(self) -> dict:
        """Score, clock, period and the headline team numbers."""
        st = self.state
        return {
            "clock": st.clock,
            "period": st.period,
            "finished": st.finished,
            "score": dict(st.score),
            "teams": {s: {"name": st.teams[s]["name"], "short": st.teams[s]["short"],
                          "xg": st.team_stats(s)["xg"], "shots": st.team_stats(s)["shots"]} for s in ("HOME", "AWAY")},
        }

    def get_team_stats(self, team: str) -> dict:
        """All team numbers for HOME or AWAY."""
        team = self._side(team)
        return {"team": team, "name": self.state.teams[team]["name"], **self.state.team_stats(team)}

    def get_player_stats(self, player: str) -> dict:
        """One player's numbers so far, by id (h-09) or name."""
        return self.state.player_stats(self._player_id(player))

    def get_sequence(self, event_id: str, max_events: int = 20) -> dict:
        """The passage of play that led up to an event: same team, back to when they won the ball."""
        events = self.state.events
        idx = next((i for i in range(len(events) - 1, -1, -1) if events[i]["id"] == event_id), None)
        if idx is None:
            raise ValueError(f"no event {event_id}")
        target = events[idx]
        team = target.get("team")
        seq = []
        for ev in reversed(events[: idx + 1]):
            if ev["type"] in ("kickoff", "half_time", "goal") and ev is not target:
                break
            if ev["type"] == "possession_change":
                if ev.get("team") == team:
                    seq.append(ev)
                break
            if ev["type"] in SEQUENCE_TYPES and ev.get("team") == team:
                seq.append(ev)
            if len(seq) >= max_events or target["t"] - ev["t"] > 60:
                break
        seq.reverse()
        passes = [e for e in seq if e["type"] == "pass" and e["outcome"] == "complete"]
        return {
            "event": target,
            "team": team,
            "events": seq,
            "passes": len(passes),
            "duration_s": round(target["t"] - seq[0]["t"], 1) if seq else 0.0,
            "players_involved": sorted({e["player"] for e in seq if e.get("player")}),
            "won_by": seq[0].get("reason") if seq and seq[0]["type"] == "possession_change" else None,
        }

    def get_trend(self, metric: str, window_minutes: int = 15) -> dict:
        """Per-minute history of xg, possession_pct, control_chaos, momentum or field_tilt."""
        if metric not in TREND_METRICS:
            raise ValueError(f"metric must be one of {TREND_METRICS}")
        return {"metric": metric, "points": self.state.trend(metric, window_minutes)}

    def compare_players(self, player_a: str, player_b: str) -> dict:
        """Two players' numbers side by side."""
        return {"a": self.get_player_stats(player_a), "b": self.get_player_stats(player_b)}

    def top_players(self, stat: str, n: int = 3) -> list[dict]:
        """Leaders for one player stat (goals, xg, top_speed_kmh, distance_m, passes, ...)."""
        rows = [self.state.player_stats(p) for p in self.state.players]
        rows = [r for r in rows if isinstance(r.get(stat), (int, float))]
        return sorted(rows, key=lambda r: r[stat], reverse=True)[:n]

    def get_recent_events(self, n: int = 10, types: list[str] | None = None) -> list[dict]:
        """The latest match events, newest last, optionally only some types (shot, goal, foul, ...)."""
        events = [e for e in self.state.events if not types or e["type"] in types]
        return events[-max(1, min(n, 100)):]

    def list_plugins(self) -> list[dict]:
        """Installed graphics plugins the Director can put on screen."""
        return list_plugins()

    # --- helpers ------------------------------------------------------------

    def _side(self, team: str) -> str:
        t = team.strip()
        for side in ("HOME", "AWAY"):
            info = self.state.teams[side]
            if t.upper() == side or t.lower() in (info["name"].lower(), info["short"].lower(), info["key"]):
                return side
        raise ValueError(f"unknown team {team!r}")

    def _player_id(self, player: str) -> str:
        """A player id from an id (h-09), a full name or an unambiguous last name."""
        if player in self.state.players:
            return player
        wanted = player.strip().lower()
        for pid, info in self.state.players.items():
            if info["name"].lower() == wanted:
                return pid
        by_last = [pid for pid, info in self.state.players.items() if info["name"].split()[-1].lower() == wanted]
        if len(by_last) == 1:
            return by_last[0]
        names = ", ".join(self.state.players[p]["name"] for p in by_last)
        raise ValueError(f"{player!r} could be {names}" if by_last else f"unknown player {player!r}")
