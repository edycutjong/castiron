"""SQLite persistence — runs / stages / events per ARCHITECTURE schema."""

from __future__ import annotations

import asyncio

from castiron.db import Database
from castiron.pipeline import run_episode


def test_schema_roundtrip_runs_stages_events(tmp_path):
    db = Database(tmp_path / "t.db")
    db.insert_run("r1", state="queued", script_sha="abc", voice="v", music_style="lofi")
    assert db.get_run("r1").state == "queued"

    db.update_run("r1", state="completed", manifest_hash="deadbeef",
                  episode_key="b2/ci-published/episode.mp3")
    run = db.get_run("r1")
    assert run.state == "completed"
    assert run.manifest_hash == "deadbeef"

    db.upsert_stage("r1", "narration", state="pending")
    db.upsert_stage("r1", "narration", state="succeeded", provider_used="lmnt",
                    model_used="lmnt-blizzard", fallback_rung=1)
    stages = db.list_stages("r1")
    assert len(stages) == 1  # upsert, not duplicate insert
    assert stages[0].state == "succeeded"
    assert stages[0].fallback_rung == 1

    e1 = db.insert_event("r1", "pipeline", "step.started", '{"x":1}')
    e2 = db.insert_event("r1", "pipeline", "step.completed", '{"x":2}')
    assert e2 > e1
    assert [e.type for e in db.list_events("r1")] == ["step.started", "step.completed"]
    # cursor semantics for SSE catch-up
    assert [e.type for e in db.list_events("r1", after_id=e1)] == ["step.completed"]
    db.close()


def test_run_episode_persists_full_state(tmp_path):
    db = Database(tmp_path / "run.db")
    asyncio.run(run_episode(store_root=tmp_path / "store", run_id="p1",
                            db=db, publish=False))
    run = db.get_run("p1")
    assert run.state == "completed"
    assert run.manifest_hash and len(run.manifest_hash) == 64
    assert run.script_sha

    stages = {s.name: s for s in db.list_stages("p1")}
    assert set(stages) == {"narration", "music", "cover"}
    assert all(s.state == "succeeded" for s in stages.values())
    assert stages["narration"].model_used == "elevenlabs-multilingual-v2"
    assert stages["cover"].b2_key and stages["cover"].b2_key.endswith(".png")
    for s in stages.values():
        assert s.sha256  # every produced asset recorded its content hash

    events = db.list_events("p1")
    assert events[0].type == "pipeline.started"
    assert events[-1].type == "pipeline.completed"
    assert [e.id for e in events] == sorted(e.id for e in events)
    db.close()


def test_failed_run_is_recorded_not_hidden(tmp_path):
    db = Database(tmp_path / "fail.db")
    r = asyncio.run(run_episode(store_root=tmp_path / "s", run_id="bad",
                                chaos="narration", db=db, publish=False))
    assert r.state == "failed"
    assert not r.ok
    run = db.get_run("bad")
    assert run.state == "failed"
    assert run.error and "exhausted" in run.error
    assert db.get_run("bad").manifest_hash is None
    db.close()
