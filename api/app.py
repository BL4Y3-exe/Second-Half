"""FastAPI app: `uvicorn api.app:app --reload` (or `python -m api`)."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.transport_security import TransportSecuritySettings

from agents.settings import foundry_settings, load_env
from mcp_server import list_plugins
from mcp_server.server import build_server
from simulator import CLUBS

from .hub import HubSource, MatchHub, MatchKey

ROOT = Path(__file__).resolve().parent.parent
WEB_DIST = ROOT / "web" / "dist"

load_env()  # FOUNDRY_* and MCP_ALLOWED_HOSTS may come from a .env file in the project root
hub = MatchHub()
mcp = build_server(HubSource(hub))


def mcp_security() -> TransportSecuritySettings:
    """Only accept MCP requests addressed to this machine, plus any public host names in MCP_ALLOWED_HOSTS
    (comma-separated, e.g. the Azure Container Apps domain). Guards against DNS rebinding."""
    extra = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    local = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[*local, *extra],
        allowed_origins=[*(f"http://{h}" for h in local), *(f"https://{h}" for h in extra)],
    )


# Streamable HTTP at /mcp. Stateless: each request stands alone, so it also works behind several replicas.
mcp_http = mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, json_response=True,
                                   transport_security=mcp_security())


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Second Half", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.router.routes.extend(mcp_http.routes)


@app.get("/api/health")
def health() -> dict:
    model = (foundry_settings() or {}).get("model", "mock")
    return {"ok": True, "live_matches": len(hub.matches), "model": model,
            "release": os.environ.get("SECOND_HALF_RELEASE", "dev")}


@app.get("/api/clubs")
def clubs() -> list[dict]:
    return [{"key": c.key, "name": c.name, "short": c.short, "colors": list(c.colors), "style": c.style,
             "formation": c.formation} for c in CLUBS.values()]


@app.get("/api/live")
async def live(
    request: Request,
    home: str = "harbourside",
    away: str = "kingsmere",
    seed: int = 9,
    speed: float = Query(10.0, ge=1.0, le=60.0),
) -> StreamingResponse:
    """Server-Sent Events: meta, frame, event, trigger, stats and end messages for one live match."""
    if home not in CLUBS or away not in CLUBS or home == away:
        raise HTTPException(400, f"pick two different clubs from {sorted(CLUBS)}")
    match = hub.get_or_start(MatchKey(home, away, seed, speed))
    queue = hub.subscribe(match)

    async def stream():
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    kind, data = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"event: {kind}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"
                if kind == "end" or await request.is_disconnected():
                    break
        finally:
            hub.unsubscribe(match, queue)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(stream(), media_type="text/event-stream", headers=headers)


# Outside plugins run in a sandboxed iframe (see web/src/plugins/Sandboxed.tsx). This policy also cuts them off
# from the network, so a plugin can only draw what the host sends it.
PLUGIN_CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; "
              "font-src data:; frame-ancestors 'self'; base-uri 'none'; form-action 'none'")


@app.get("/plugins/{plugin_id}/{filename}", include_in_schema=False)
def plugin_file(plugin_id: str, filename: str) -> FileResponse:
    """The entry page of an installed outside plugin, and nothing else from the plugins folder."""
    manifest = next((p for p in list_plugins() if p["id"] == plugin_id and not p.get("builtin")), None)
    path = ROOT / "plugins" / plugin_id / filename
    if manifest is None or filename != manifest.get("entry") or not path.is_file():
        raise HTTPException(404, "no such plugin file")
    headers = {"Content-Security-Policy": PLUGIN_CSP, "X-Content-Type-Options": "nosniff",
               "Referrer-Policy": "no-referrer", "Cache-Control": "no-cache"}
    return FileResponse(path, media_type="text/html", headers=headers)


# Serve the built web app (npm run build) from the same server when it exists.
if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        file = (WEB_DIST / path).resolve()
        inside = file.is_relative_to(WEB_DIST.resolve())  # no ../ escapes out of the build folder
        return FileResponse(file if path and inside and file.is_file() else WEB_DIST / "index.html")
