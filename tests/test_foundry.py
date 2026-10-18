"""The Foundry model path, without Azure: a local stand-in for the Foundry Responses endpoint."""

import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from agent_framework.foundry import FoundryChatClient
from azure.core.credentials import AccessTokenInfo

from agents import MockModel
from agents import foundry as foundry_module
from agents.director import Director
from agents.foundry import FoundryModel
from agents.models import _foundry, explain_failure, load_model
from agents.settings import load_env
from agents.types import Moment
from tests.test_agents import run_match


class FakeFoundry(BaseHTTPRequestHandler):
    """Answers POST .../openai/v1/responses the way Foundry does, and remembers what it was sent."""

    requests: list[tuple[str, dict]] = []
    reply = "Holloway scores."
    status = 200

    def do_POST(self):  # noqa: N802 - the name http.server looks for
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeFoundry.requests.append((self.path, body))
        if FakeFoundry.status != 200:
            out = json.dumps({"error": {"code": "Failed", "message": f"status {FakeFoundry.status}"}}).encode()
            self.send_response(FakeFoundry.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return
        out = json.dumps({
            "id": "resp_1", "object": "response", "created_at": int(time.time()), "status": "completed",
            "model": body["model"],
            "output": [{"type": "message", "id": "msg_1", "status": "completed", "role": "assistant",
                        "content": [{"type": "output_text", "text": FakeFoundry.reply, "annotations": []}]}],
            "usage": {"input_tokens": 10, "output_tokens": 3, "total_tokens": 13},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


class FakeCredential:
    scopes: list[str] = []

    async def get_token_info(self, *scopes, options=None):
        FakeCredential.scopes += scopes
        return AccessTokenInfo("token", int(time.time()) + 3600)

    async def get_token(self, *scopes, **kwargs):
        return await self.get_token_info(*scopes)

    async def close(self):
        pass


@pytest.fixture(scope="module")
def endpoint():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeFoundry)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/api/projects/second-half"
    server.shutdown()


def foundry_model(endpoint: str, **kwargs) -> FoundryModel:
    client = FoundryChatClient(project_endpoint=endpoint, model="gpt-5.4-mini", credential=FakeCredential())
    return FoundryModel(model="gpt-5.4-mini", client=client, **kwargs)


def test_each_writer_runs_as_an_agent_on_the_foundry_responses_api(endpoint):
    FakeFoundry.requests.clear()
    model = foundry_model(endpoint)

    async def run():
        a = await model.complete("storyteller", "You are the Storyteller.", "Moment: goal", {})
        b = await model.complete("persona", "You are the Persona agent.", "Mode: casual", {})
        c = await model.complete("storyteller", "You are the Storyteller.", "Moment: big chance", {})
        return a, b, c

    assert asyncio.run(run()) == ("Holloway scores.",) * 3
    assert set(model.agents) == {"storyteller", "persona"}  # one Agent Framework agent per writer, reused
    assert "https://ai.azure.com/.default" in FakeCredential.scopes
    path, body = FakeFoundry.requests[0]
    assert path == "/api/projects/second-half/openai/v1/responses"
    assert body["model"] == "gpt-5.4-mini" and body["instructions"] == "You are the Storyteller."
    assert body["reasoning"] == {"effort": "low"} and body["store"] is False
    assert FakeFoundry.requests[1][1]["instructions"] == "You are the Persona agent."
    # Each line is a one-off: no earlier drafts are sent along.
    assert [m["content"][0]["text"] for m in FakeFoundry.requests[2][1]["input"]] == ["Moment: big chance"]


def test_reasoning_can_be_turned_off_for_models_without_it(endpoint):
    FakeFoundry.requests.clear()
    asyncio.run(foundry_model(endpoint, reasoning_effort="").complete("recap", "You are the Recap agent.", "Go", {}))
    assert "reasoning" not in FakeFoundry.requests[0][1]


def test_empty_or_slow_answers_raise(endpoint, monkeypatch):
    model = foundry_model(endpoint)
    monkeypatch.setattr(FakeFoundry, "reply", "  ")
    with pytest.raises(RuntimeError, match="no text"):
        asyncio.run(model.complete("storyteller", "You are the Storyteller.", "Moment: goal", {}))

    class Slow:
        async def run(self, prompt):
            await asyncio.sleep(1)

    monkeypatch.setattr(foundry_module, "TIMEOUT_S", 0.05)
    monkeypatch.setattr(model, "agent", lambda name, instructions: Slow())
    with pytest.raises(TimeoutError):
        asyncio.run(model.complete("storyteller", "You are the Storyteller.", "Moment: goal", {}))


@pytest.mark.parametrize("status, says", [(403, "Foundry User role"), (404, "deployment name")])
def test_set_up_problems_are_explained(endpoint, monkeypatch, status, says):
    monkeypatch.setattr(FakeFoundry, "status", status)
    with pytest.raises(Exception) as caught:
        asyncio.run(foundry_model(endpoint).complete("storyteller", "You are the Storyteller.", "Moment: goal", {}))
    assert says in explain_failure(caught.value)


def test_settings_pick_foundry_only_when_configured(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# Foundry\nFOUNDRY_PROJECT_ENDPOINT="https://x.services.ai.azure.com/api/projects/p"\n'
                   "FOUNDRY_MODEL=gpt-5.4-mini\nexport FOUNDRY_REASONING_EFFORT='none'\n", encoding="utf-8")
    for key in ("FOUNDRY_PROJECT_ENDPOINT", "FOUNDRY_MODEL", "FOUNDRY_REASONING_EFFORT"):
        monkeypatch.delenv(key, raising=False)
    assert isinstance(load_model(seed=3), MockModel)
    with pytest.raises(ValueError, match="FOUNDRY_PROJECT_ENDPOINT"):
        load_model(use="foundry")

    monkeypatch.setenv("FOUNDRY_MODEL", "my-deployment")  # already set: the .env file doesn't override it
    load_env(env)
    _foundry.cache_clear()
    model = load_model(seed=3)
    assert isinstance(model, FoundryModel) and model.name == "my-deployment"
    assert model.options["reasoning"] == {"effort": "none"}
    assert load_model(seed=4) is model  # every match shares one client
    assert isinstance(load_model(use="mock"), MockModel)
    _foundry.cache_clear()


class BrokenModel(MockModel):
    """A model that never answers: quota used up, network down."""

    async def complete(self, agent, system, prompt, context):
        raise ConnectionError("Foundry unreachable")


def test_without_a_model_the_studio_still_puts_checked_graphics_on_screen():
    orch, published = run_match(seed=9, model=BrokenModel(seed=9), until=3000)
    overlays = [d for kind, d in published if kind == "overlay"]
    stories = [d for d in overlays if d["kind"] != "recap"]
    assert stories and all(d["fallback"] and d["plugin"] == "stat-card" for d in stories)
    assert all(d["fallback_reason"] == "no_answer" for d in stories)
    recap = next(d for d in overlays if d["kind"] == "recap")
    assert recap["text"]["es"]["casual"].startswith("Descanso")  # the scripted Spanish recap
    for d in overlays:
        assert {lang: set(texts) for lang, texts in d["text"].items()} == {
            "en": {"analyst", "casual", "player"}, "es": {"analyst", "casual", "player"}}
    trace = [d for kind, d in published if kind == "trace"]
    assert any(s["agent"] == "storyteller" and s["action"] == "no answer" for s in trace)
    assert any(s["agent"] == "recap" and s["action"] == "no answer" for s in trace)
    assert not any(s["action"] == "redrafted (2)" for s in trace)  # no retrying a model that is down


def test_moments_the_team_is_too_late_for_are_dropped():
    director = Director(speed=10)
    chance = Moment("m-1", "big_chance", 600.0, "10:00", 2, "HOME", None, "Big chance", {})
    goal = Moment("m-2", "goal", 600.0, "10:00", 1, "HOME", None, "Goal", {})
    assert director.too_late(chance, now=700.0) is None  # 10 s later at x10
    assert "too late" in director.too_late(chance, now=900.0)  # 30 s later
    assert director.too_late(goal, now=900.0) is None  # goals always go out


class SlowRecapModel(MockModel):
    """Takes its time over recaps, the way a real model does."""

    async def complete(self, agent, system, prompt, context):
        if agent == "recap":
            await asyncio.sleep(1.0)
        return await super().complete(agent, system, prompt, context)


def test_full_time_waits_for_the_last_recap(monkeypatch):
    from api import hub as hub_module

    monkeypatch.setattr(hub_module, "load_model", lambda seed: SlowRecapModel(seed=seed))

    async def watch() -> list[str]:
        hub = hub_module.MatchHub()
        live = hub.get_or_start(hub_module.MatchKey("harbourside", "kingsmere", 9, 100000.0))
        q = hub.subscribe(live)
        seen: list[str] = []
        while True:
            kind, data = await asyncio.wait_for(q.get(), timeout=120)
            if kind == "overlay" and data["kind"] == "recap":
                seen.append(data["headline"])
            if kind == "end":
                live.task.cancel()
                live.agents_task.cancel()
                return seen

    assert asyncio.run(watch()) == ["HALF TIME", "FULL TIME"]
