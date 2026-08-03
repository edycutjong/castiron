"""CastIron FastAPI backend — P1 core flow.

New in P1:
- ``POST /runs``            create a run; the real pipeline runner fans narration
                            (cross-provider ladder) + music + cover out in parallel.
- ``GET  /runs/{id}``       run state + stages + manifest summary (from SQLite).
- ``GET  /runs/{id}/events``SSE relay of the pipeline stream events (durable,
                            ordered, reconnect-safe) that fills the UI stage rail.
- ``GET  /console``         minimal EventSource stage-rail page (SSE contract demo).

P0 surface (``/healthz``, ``/``, ``/integrations/verify``) is retained.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from castiron import __version__, webhooks
from castiron.backends import LocalDirBackend
from castiron.config import settings
from castiron.db import Database, default_db_url, get_db, set_db
from castiron.hub import hub
from castiron.pipeline import STAGE_ORDER, _script_sha, run_episode

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def _genblaze_version() -> str:
    import importlib.metadata as _md

    try:
        return _md.version("genblaze")
    except _md.PackageNotFoundError:  # pragma: no cover
        return "unknown"


def _ffmpeg_present() -> bool:
    from castiron.media import ffmpeg_available

    return ffmpeg_available()


app = FastAPI(
    title="CastIron",
    version=__version__,
    description="Self-healing audio-episode factory on Genblaze + Backblaze B2.",
)


@app.on_event("startup")
def _startup() -> None:
    # Bind a persistent file-backed DB for the running service.
    set_db(Database(default_db_url()))


# --------------------------------------------------------------------------- #
# Health / info
# --------------------------------------------------------------------------- #
@app.get("/healthz")
def healthz() -> dict:
    return {
        "status": "ok",
        "service": "castiron",
        "version": __version__,
        "mode": settings.mode,
        "genblaze_version": _genblaze_version(),
        "ffmpeg": _ffmpeg_present(),
    }


@app.get("/")
def root() -> dict:
    return {
        "name": "CastIron",
        "tagline": "script to published episode, even when your TTS provider dies",
        "mode": settings.mode,
        "console": "/console",
        "docs": "/docs",
        "health": "/healthz",
        "integrations": "/integrations/verify",
    }


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #
class RunRequest(BaseModel):
    script: str | None = None
    voice: str = "narrator"
    music_style: str = "ambient"
    chaos: str | None = None


async def _run_background(run_id: str, req: RunRequest) -> None:
    from castiron.pipeline import DEFAULT_SCRIPT

    try:
        await run_episode(
            run_id=run_id,
            script=req.script or DEFAULT_SCRIPT,
            voice=req.voice,
            music_style=req.music_style,
            chaos=req.chaos,
            db=get_db(),
            hub=hub,
            publish=True,
        )
    except Exception:  # noqa: BLE001 — errors are already recorded on the run row
        get_db().update_run(run_id, state="failed")
    finally:
        hub.mark_done(run_id)


@app.post("/runs", status_code=202)
async def create_run(req: RunRequest) -> JSONResponse:
    db = get_db()
    run_id = uuid.uuid4().hex[:12]
    script = req.script or ""
    db.insert_run(
        run_id, state="queued", script_sha=_script_sha(script or "-"),
        voice=req.voice, music_style=req.music_style, chaos_flag=req.chaos,
    )
    for name in STAGE_ORDER:
        db.upsert_stage(run_id, name, state="pending")
    # Fire-and-forget: the runner streams events into the DB + hub.
    asyncio.create_task(_run_background(run_id, req))
    return JSONResponse(
        status_code=202,
        content={
            "run_id": run_id,
            "state": "queued",
            "stages": list(STAGE_ORDER),
            "events": f"/runs/{run_id}/events",
            "self": f"/runs/{run_id}",
        },
    )


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    db = get_db()
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown run")
    stages = db.list_stages(run_id)
    return {
        "run": {
            "id": run.id, "state": run.state, "created_at": run.created_at,
            "voice": run.voice, "music_style": run.music_style,
            "chaos": run.chaos_flag, "episode_key": run.episode_key,
            "manifest_hash": run.manifest_hash, "error": run.error,
        },
        "stages": [
            {
                "name": s.name, "state": s.state, "provider_used": s.provider_used,
                "model_used": s.model_used, "fallback_rung": s.fallback_rung,
                "b2_key": s.b2_key, "sha256": s.sha256,
            }
            for s in stages
        ],
        "manifest": {"hash": run.manifest_hash} if run.manifest_hash else None,
    }


def _sse(event_type: str, data) -> str:
    body = data if isinstance(data, str) else json.dumps(data)
    return f"event: {event_type}\ndata: {body}\n\n"


@app.get("/runs/{run_id}/events")
async def run_events(run_id: str) -> StreamingResponse:
    db = get_db()
    if db.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="unknown run")

    async def stream():
        # Subscribe first so live wakeups are never missed; the DB is the ordered,
        # durable, dedup-free source of event CONTENT — the hub is only a nudge to
        # re-poll promptly (so live updates surface in ms, not at poll cadence).
        q = hub.subscribe(run_id)
        last_id = 0
        try:
            yield _sse("open", {"run_id": run_id})
            while True:
                for e in db.list_events(run_id, after_id=last_id):
                    last_id = e.id
                    yield _sse(e.type, e.payload_json)
                run = db.get_run(run_id)
                terminal = bool(run and run.state in ("completed", "failed"))
                if terminal and not db.list_events(run_id, after_id=last_id):
                    yield _sse("done", {"state": run.state,
                                        "manifest_hash": run.manifest_hash})
                    return
                try:
                    await asyncio.wait_for(q.get(), timeout=0.25)
                except TimeoutError:
                    pass
        finally:
            hub.unsubscribe(run_id, q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# --------------------------------------------------------------------------- #
# Console (static EventSource stage-rail page)
# --------------------------------------------------------------------------- #
@app.get("/console")
def console() -> FileResponse:
    page = WEB_DIR / "console.html"
    if not page.is_file():  # pragma: no cover
        raise HTTPException(status_code=404, detail="console not built")
    return FileResponse(page, media_type="text/html")


# --------------------------------------------------------------------------- #
# Integrations dashboard
# --------------------------------------------------------------------------- #
@app.post("/webhooks/b2")
async def webhooks_b2(request: Request) -> JSONResponse:
    """B2 Event Notification receiver (P3) — HMAC-verified, idempotent.

    Drives the event-driven stage machine: object-created events advance a run
    render → mix → verify → publish (invariant I1). OFFLINE this is exercised
    with synthetic payloads; LIVE it is the real B2 rule firing (P3 + creds).
    """
    body = await request.body()
    sig = request.headers.get(webhooks.SIGNATURE_HEADER)
    secret = os.environ.get("WEBHOOK_HMAC_SECRET")
    try:
        result = webhooks.handle_delivery(get_db(), body, sig, secret)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail="bad signature") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(result)


@app.get("/integrations/verify")
def integrations_verify() -> JSONResponse:
    db = get_db()
    payload: dict = {
        "mode": settings.mode,
        "media_bucket": settings.media_bucket,
        "published_bucket": settings.published_bucket,
        "max_run_cost_usd": settings.max_run_cost_usd,
        "runs_tracked": len(db.list_runs(limit=1000)),
    }
    if settings.offline:
        store = settings.local_store
        payload["local_store"] = str(store)
        if store.exists():
            backend = LocalDirBackend(store)
            entries = backend.list().entries
            payload["object_count"] = len(entries)
            payload["sample_keys"] = [e.key for e in entries[:10]]
        else:
            payload["object_count"] = 0
            payload["sample_keys"] = []
    return JSONResponse(payload)
