"""SSE relay: GET /runs/{id}/events streams the pipeline events in order."""

from __future__ import annotations

import asyncio
import json

import pytest

from castiron.db import Database, set_db
from castiron.pipeline import run_offline_episode


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    """Parse an SSE body into (event_name, data_dict) pairs."""
    out: list[tuple[str, dict]] = []
    for block in text.strip().split("\n\n"):
        name, data = None, None
        for line in block.splitlines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                raw = line[5:].strip()
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    data = {"_raw": raw}
        if name:
            out.append((name, data or {}))
    return out


def test_sse_replays_durable_log_in_order(tmp_db, tmp_path):
    # Produce a run into the bound DB (publish off); the run is terminal in the DB.
    run_offline_episode(store_root=tmp_path / "store", run_id="s1", db=tmp_db)

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)  # plain client → no lifespan/startup rebind
    body = client.get("/runs/s1/events").text

    events = _parse_sse(body)
    names = [n for n, _ in events]
    assert names[0] == "open"
    assert names[-1] == "done"

    structural = [n for n in names if n in
                  ("pipeline.started", "step.started", "step.completed", "pipeline.completed")]
    assert structural[0] == "pipeline.started"
    assert structural[-1] == "pipeline.completed"
    assert structural.count("step.started") == 3
    assert structural.count("step.completed") == 3

    # per-stage ordering: each stage starts before it completes
    started, completed = {}, {}
    for i, (name, data) in enumerate(events):
        if name == "step.started":
            started[data.get("step_index")] = i
        elif name == "step.completed":
            completed[data.get("step_index")] = i
    for idx in (0, 1, 2):
        assert started[idx] < completed[idx]


def test_sse_done_carries_manifest_hash(tmp_db, tmp_path):
    run_offline_episode(store_root=tmp_path / "store", run_id="s2", db=tmp_db)
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    events = _parse_sse(client.get("/runs/s2/events").text)
    done = dict(events)["done"]
    assert done["state"] == "completed"
    assert len(done["manifest_hash"]) == 64


def test_sse_unknown_run_404(tmp_db):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.get("/runs/nope/events").status_code == 404


@pytest.mark.asyncio
async def test_post_runs_then_live_sse_ordering(tmp_path):
    """End-to-end live path: POST /runs kicks the background runner; the SSE
    endpoint tails the events to completion."""
    import httpx

    db = Database(tmp_path / "live.db")
    set_db(db)
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/runs", json={"script": "live", "chaos": "tts"})
        assert resp.status_code == 202
        run_id = resp.json()["run_id"]

        collected: list[tuple[str, dict]] = []
        async def _drain():
            async with client.stream("GET", f"/runs/{run_id}/events") as r:
                buf = ""
                async for chunk in r.aiter_text():
                    buf += chunk
                    while "\n\n" in buf:
                        block, buf = buf.split("\n\n", 1)
                        parsed = _parse_sse(block + "\n\n")
                        if parsed:
                            collected.append(parsed[0])
                            if parsed[0][0] == "done":
                                return

        await asyncio.wait_for(_drain(), timeout=15)

    names = [n for n, _ in collected]
    assert "pipeline.started" in names
    assert names.count("step.completed") == 3
    assert names[-1] == "done"
    # chaos=tts → narration fell back to lmnt, visible in the stream
    completed = [d for n, d in collected if n == "step.completed"]
    narration = next(d for d in completed if d.get("stage") == "narration")
    assert narration.get("model") == "lmnt-blizzard"
    assert narration.get("fell_back") is True
    db.close()
