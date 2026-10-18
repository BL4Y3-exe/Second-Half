"""The match tools over the Model Context Protocol.

Two ways to reach it:

- Inside the live server: `python -m api` serves it at http://127.0.0.1:8000/mcp
  (Streamable HTTP). It answers about the matches people are watching.
- On its own over stdio: `python -m mcp_server --seed 9 --minute 60` plays that
  match up to the minute given and answers about it. Handy for trying the tools
  from an MCP client without the web app.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, Protocol, TypeVar

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from stats import MatchState

from .tools import MatchTools
from .tools import list_plugins as installed_plugins

INSTRUCTIONS = """\
Live data for a synthetic football match (all clubs and players are fictional).
Every number comes from the match simulator's stats engine, so quote them as given.
Most tools take an optional match_id; leave it out to ask about the match that started most recently.
Players can be named by id (h-09), full name or last name; teams by HOME, AWAY, name or short name (HAR).
Event ids (e-00123) come from get_recent_events and are what get_sequence takes."""


class Match(Protocol):
    """One match the server can answer about."""

    state: MatchState
    overlays: list[dict]  # what the studio has put on screen so far


class MatchSource(Protocol):
    def matches(self) -> list[dict]:
        """Summary rows: id, clubs, score, clock, finished."""
        ...

    def lookup(self, match_id: str | None) -> Match:
        """The match with this id, or the latest one when None. Raises ValueError if there is none."""
        ...


F = TypeVar("F", bound=Callable[..., Any])


def explain_errors(fn: F) -> F:
    """Lets a bad name or id reach the client as a readable tool error instead of a generic crash."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    return wrapper  # type: ignore[return-value]


def summary(match_id: str, state: MatchState) -> dict:
    return {
        "match_id": match_id,
        "home": state.teams["HOME"]["name"],
        "away": state.teams["AWAY"]["name"],
        "score": f"{state.teams['HOME']['short']} {state.score['HOME']}-{state.score['AWAY']} "
                 f"{state.teams['AWAY']['short']}",
        "clock": state.clock,
        "period": state.period,
        "finished": state.finished,
    }


def build_server(source: MatchSource) -> MCPServer:
    server = MCPServer(name="second-half", title="Second Half match data", version="0.1.0",
                       instructions=INSTRUCTIONS)

    def tools(match_id: str | None) -> MatchTools:
        return MatchTools(source.lookup(match_id).state)

    @server.tool()
    @explain_errors
    def list_matches() -> list[dict[str, Any]]:
        """Matches this server knows about: id, clubs, score, clock and whether they have finished."""
        return source.matches()

    @server.tool()
    @explain_errors
    def get_score(match_id: str | None = None) -> dict[str, Any]:
        """Score, clock and period, with each team's xG and shots."""
        return tools(match_id).get_score()

    @server.tool()
    @explain_errors
    def get_team_stats(team: str, match_id: str | None = None) -> dict[str, Any]:
        """All numbers for one team: xG, shots, passes, possession, field tilt, PPDA, distance and more."""
        return tools(match_id).get_team_stats(team)

    @server.tool()
    @explain_errors
    def get_player_stats(player: str, match_id: str | None = None) -> dict[str, Any]:
        """One player's numbers so far: goals, xG, passes, top speed, distance and more."""
        return tools(match_id).get_player_stats(player)

    @server.tool()
    @explain_errors
    def compare_players(player_a: str, player_b: str, match_id: str | None = None) -> dict[str, Any]:
        """Two players' numbers side by side."""
        return tools(match_id).compare_players(player_a, player_b)

    @server.tool()
    @explain_errors
    def top_players(stat: str, n: int = 3, match_id: str | None = None) -> list[dict[str, Any]]:
        """Leaders for one player stat, such as goals, xg, top_speed_kmh, distance_m or passes."""
        return tools(match_id).top_players(stat, n)

    @server.tool()
    @explain_errors
    def get_recent_events(n: int = 10, types: list[str] | None = None,
                          match_id: str | None = None) -> list[dict[str, Any]]:
        """The latest match events, newest last. Optionally only some types: pass, shot, goal, foul, tackle..."""
        return tools(match_id).get_recent_events(n, types)

    @server.tool()
    @explain_errors
    def get_sequence(event_id: str, max_events: int = 20, match_id: str | None = None) -> dict[str, Any]:
        """The passage of play that led up to an event, back to when the team won the ball."""
        return tools(match_id).get_sequence(event_id, max_events)

    @server.tool()
    @explain_errors
    def get_trend(metric: str, window_minutes: int = 15, match_id: str | None = None) -> dict[str, Any]:
        """Minute-by-minute history of xg, possession_pct, control_chaos, momentum or field_tilt."""
        return tools(match_id).get_trend(metric, window_minutes)

    @server.tool()
    @explain_errors
    def get_on_screen(n: int = 5, match_id: str | None = None) -> list[dict[str, Any]]:
        """The graphics the agent team has put on screen most recently, with their fact-checked stories."""
        overlays = source.lookup(match_id).overlays[-max(1, min(n, 50)):]
        keep = ("id", "clock", "kind", "plugin", "headline", "story", "fallback")
        return [{k: o.get(k) for k in keep} for o in overlays]

    @server.tool()
    @explain_errors
    def list_plugins() -> list[dict[str, Any]]:
        """Installed graphics plugins: what each needs, where it goes on screen and for how long."""
        return installed_plugins()

    return server
