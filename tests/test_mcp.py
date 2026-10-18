import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from mcp import Client

from api.app import app
from mcp_server.__main__ import OneMatch, play
from mcp_server.server import build_server

TOOLS = {"list_matches", "get_score", "get_team_stats", "get_player_stats", "compare_players", "top_players",
         "get_recent_events", "get_sequence", "get_trend", "get_on_screen", "list_plugins"}
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


@pytest.fixture(scope="module")
def played():
    return asyncio.run(play("harbourside", "kingsmere", seed=9, minute=50))


def call_all(played, calls: list[tuple[str, dict]]):
    async def run():
        async with Client(build_server(OneMatch(played))) as client:
            listed = {t.name for t in (await client.list_tools()).tools}
            results = [await client.call_tool(name, args) for name, args in calls]
            return listed, results

    return asyncio.run(run())


def text(result) -> str:
    return result.content[0].text


def test_tools_answer_from_match_state(played):
    state = played.state
    goal = next(e for e in state.events if e["type"] == "goal")
    scorer = state.players[goal["player"]]["name"]
    listed, (score, player, seq, on_screen, trend) = call_all(played, [
        ("get_score", {}),
        ("get_player_stats", {"player": scorer}),
        ("get_sequence", {"event_id": goal["id"]}),
        ("get_on_screen", {"n": 3}),
        ("get_trend", {"metric": "momentum", "window_minutes": 10}),
    ])
    assert listed == TOOLS
    assert not any(r.is_error for r in (score, player, seq, on_screen, trend))
    assert json.loads(text(score))["score"] == state.score
    assert json.loads(text(player))["goals"] >= 1
    assert seq.structured_content["event"]["id"] == goal["id"]
    assert len(on_screen.structured_content["result"]) == 3
    assert trend.structured_content["points"]


def test_bad_names_come_back_as_readable_errors(played):
    _, (unknown, bad_metric, other_match) = call_all(played, [
        ("get_player_stats", {"player": "Nobody Atall"}),
        ("get_trend", {"metric": "vibes"}),
        ("get_score", {"match_id": "some-other-match"}),
    ])
    assert unknown.is_error and "unknown player 'Nobody Atall'" in text(unknown)
    assert bad_metric.is_error and "metric must be one of" in text(bad_metric)
    assert other_match.is_error and "no match 'some-other-match'" in text(other_match)


def test_live_server_serves_mcp_over_http():
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        r = client.post("/mcp", json=body, headers=HEADERS)
        assert r.status_code == 200
        assert {t["name"] for t in r.json()["result"]["tools"]} == TOOLS

        call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_score", "arguments": {}}}
        r = client.post("/mcp", json=call, headers=HEADERS)
        result = r.json()["result"]
        assert result["isError"] and "no match is running" in result["content"][0]["text"]

        # Requests addressed to some other host name are refused (DNS rebinding guard).
        r = client.post("/mcp", json=body, headers={**HEADERS, "Host": "evil.example.com"})
        assert r.status_code == 421
