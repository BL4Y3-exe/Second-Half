import asyncio

from fastapi.testclient import TestClient

from api.app import app
from api.hub import MatchHub, MatchKey

client = TestClient(app)


def test_health_and_clubs():
    assert client.get("/api/health").json()["ok"] is True
    clubs = client.get("/api/clubs").json()
    assert {c["key"] for c in clubs} >= {"harbourside", "kingsmere"}


def test_live_rejects_bad_clubs():
    assert client.get("/api/live?home=harbourside&away=harbourside").status_code == 400
    assert client.get("/api/live?home=nowhere").status_code == 400


def test_hub_streams_a_live_match():
    async def watch() -> dict[str, int]:
        hub = MatchHub()
        live = hub.get_or_start(MatchKey("harbourside", "kingsmere", 5, 60.0))
        q = hub.subscribe(live)
        seen: dict[str, int] = {}
        while seen.get("frame", 0) < 10 or "stats" not in seen:
            kind, data = await asyncio.wait_for(q.get(), timeout=10)
            seen[kind] = seen.get(kind, 0) + 1
            if kind == "meta":
                assert set(data["teams"]) == {"HOME", "AWAY"}
            if kind == "frame":
                assert len(data["p"]) == 22
        # A second viewer of the same match shares it instead of starting another.
        assert hub.get_or_start(MatchKey("harbourside", "kingsmere", 5, 60.0)) is live
        hub.unsubscribe(live, q)
        await asyncio.sleep(0)
        assert live.key not in hub.matches
        return seen

    seen = asyncio.run(watch())
    assert seen["meta"] == 1
    assert seen.get("event", 0) > 0


def test_outside_plugins_are_served_locked_down():
    r = client.get("/plugins/xg-race/index.html")
    assert r.status_code == 200
    csp = r.headers["content-security-policy"]
    assert "default-src 'none'" in csp and "connect-src" not in csp  # no network: default-src covers fetch too
    # Only an outside plugin's entry page is served: not manifests, not built-in plugins.
    assert client.get("/plugins/xg-race/manifest.json").status_code == 404
    assert client.get("/plugins/goal-card/index.html").status_code == 404


def test_web_app_route_stays_inside_the_build_folder():
    r = client.get("/..%2F..%2Fpyproject.toml")
    assert "second-half" not in r.text
