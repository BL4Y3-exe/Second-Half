import asyncio

from fastapi.testclient import TestClient

from api.app import app
from api.hub import MatchHub, MatchKey

client = TestClient(app)


def test_health_and_clubs():
    health = client.get("/api/health").json()
    assert health["ok"] is True and health["model"] == "mock" and health["release"] == "dev"
    clubs = client.get("/api/clubs").json()
    assert {c["key"] for c in clubs} >= {"harbourside", "kingsmere"}


def test_live_rejects_bad_clubs():
    assert client.get("/api/live?home=harbourside&away=harbourside").status_code == 400
    assert client.get("/api/live?home=nowhere").status_code == 400


def test_hub_streams_a_live_match():
    async def watch() -> dict[str, int]:
        hub = MatchHub(grace_s=0)
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


def test_a_viewer_who_reconnects_finds_the_same_match():
    async def drop_and_rejoin() -> None:
        hub = MatchHub(grace_s=0.5)
        key = MatchKey("harbourside", "kingsmere", 6, 60.0)
        live = hub.get_or_start(key)
        hub.unsubscribe(live, hub.subscribe(live))  # the stream drops...
        await asyncio.sleep(0.1)
        assert hub.get_or_start(key) is live  # ...and the viewer is back before the grace period ends
        q = hub.subscribe(live)
        await asyncio.sleep(0.6)
        assert key in hub.matches and not live.task.done()
        hub.unsubscribe(live, q)  # this time nobody comes back
        await asyncio.sleep(0.6)
        assert key not in hub.matches and live.task.done()

    asyncio.run(drop_and_rejoin())
