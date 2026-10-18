"""FastAPI app: `uvicorn api.app:app --reload` (or `python -m api`)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from simulator import CLUBS

from .hub import MatchHub, MatchKey

ROOT = Path(__file__).resolve().parent.parent
WEB_DIST = ROOT / "web" / "dist"

app = FastAPI(title="Second Half", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
hub = MatchHub()


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "live_matches": len(hub.matches)}


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


# Serve the built web app (npm run build) from the same server when it exists.
if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        file = WEB_DIST / path
        return FileResponse(file if path and file.is_file() else WEB_DIST / "index.html")
