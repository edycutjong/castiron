"""Targeted tests closing the last coverage gaps to 100%.

Each test names the module + behavior it pins; grouped by module. These exercise
error paths, defensive branches, the LIVE-mode backend factory (via a mocked
``genblaze_s3``), and a handful of small helpers the happy-path suites skip.
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
import types
from pathlib import Path

import pytest
from genblaze_core import Modality
from genblaze_core.exceptions import ProviderError
from genblaze_core.models.enums import ProviderErrorCode
from genblaze_core.models.step import Step


# --------------------------------------------------------------------------- #
# config.py
# --------------------------------------------------------------------------- #
def test_has_b2_creds_both_present_and_absent(monkeypatch):
    from castiron import config

    monkeypatch.delenv("B2_KEY_ID", raising=False)
    monkeypatch.delenv("B2_APP_KEY", raising=False)
    assert config._has_b2_creds() is False

    monkeypatch.setenv("B2_KEY_ID", "k")
    monkeypatch.setenv("B2_APP_KEY", "s")
    assert config._has_b2_creds() is True


# --------------------------------------------------------------------------- #
# hub.py
# --------------------------------------------------------------------------- #
def test_hub_is_done_and_reset():
    from castiron.hub import EventHub

    h = EventHub()
    assert h.is_done("r") is False
    h.mark_done("r")
    assert h.is_done("r") is True
    h.reset("r")
    assert h.is_done("r") is False


# --------------------------------------------------------------------------- #
# ladder.py
# --------------------------------------------------------------------------- #
def test_err_code_returns_none_for_non_enum_code():
    from castiron import ladder

    exc = ProviderError("no typed code", error_code=None)
    assert ladder._err_code(exc) is None


# --------------------------------------------------------------------------- #
# providers.py
# --------------------------------------------------------------------------- #
def test_local_tts_raises_for_unavailable_model(tmp_path):
    from castiron.providers import LocalTTSProvider

    audio = tmp_path / "n.mp3"
    audio.write_bytes(b"ID3")
    prov = LocalTTSProvider(audio, unavailable=frozenset({"eleven_multilingual_v2"}))
    step = Step(provider="local-tts", model="eleven_multilingual_v2",
                modality=Modality.AUDIO, prompt="hi")
    with pytest.raises(ProviderError) as ei:
        prov.generate(step)
    assert ei.value.error_code == ProviderErrorCode.MODEL_ERROR


# --------------------------------------------------------------------------- #
# media.py
# --------------------------------------------------------------------------- #
def test_synth_tone_requires_ffmpeg(monkeypatch, tmp_path):
    from castiron import media

    monkeypatch.setattr(media, "ffmpeg_available", lambda: False)
    with pytest.raises(media.FfmpegMissingError):
        media.synth_tone(tmp_path / "t.mp3")


def test_synth_png_requires_ffmpeg(monkeypatch, tmp_path):
    from castiron import media

    monkeypatch.setattr(media, "ffmpeg_available", lambda: False)
    with pytest.raises(media.FfmpegMissingError):
        media.synth_png(tmp_path / "c.png")


def test_synth_png_label_falls_back_when_drawtext_fails(monkeypatch, tmp_path):
    """The labeled (drawtext) path retries without the filter if ffmpeg rejects it."""
    from castiron import media

    out = tmp_path / "labeled.png"
    calls = {"n": 0}
    real_run = subprocess.run

    def fake_run(cmd, *a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            # first attempt (with drawtext) fails → triggers the plain retry
            raise subprocess.CalledProcessError(1, cmd)
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(media.subprocess, "run", fake_run)
    media.synth_png(out, label="CastIron")
    assert out.is_file()
    assert calls["n"] == 2


def test_verify_file_no_handler(tmp_path):
    from castiron import media

    with pytest.raises(ValueError, match="no media handler"):
        media.verify_file(tmp_path / "notes.txt")


def test_extract_manifest_no_handler(tmp_path):
    from castiron import media

    with pytest.raises(ValueError, match="no media handler"):
        media.extract_manifest(tmp_path / "notes.txt")


# --------------------------------------------------------------------------- #
# backends.py — LIVE (S3) branch via a mocked genblaze_s3
# --------------------------------------------------------------------------- #
def test_make_media_backend_live_uses_s3(monkeypatch, tmp_path):
    from castiron import backends
    from castiron.config import settings

    sentinel = object()
    captured = {}

    class _FakeS3:
        @classmethod
        def for_backblaze(cls, bucket, *, key_id, app_key, preflight):
            captured.update(bucket=bucket, key_id=key_id,
                            app_key=app_key, preflight=preflight)
            return sentinel

    fake_mod = types.ModuleType("genblaze_s3")
    fake_mod.S3StorageBackend = _FakeS3
    monkeypatch.setitem(sys.modules, "genblaze_s3", fake_mod)
    monkeypatch.setenv("B2_KEY_ID", "kid")
    monkeypatch.setenv("B2_APP_KEY", "secret")

    live = dataclasses.replace(settings, offline=False)
    got = backends.make_media_backend(tmp_path, settings=live)
    assert got is sentinel
    assert captured == {"bucket": live.media_bucket, "key_id": "kid",
                        "app_key": "secret", "preflight": False}


# --------------------------------------------------------------------------- #
# db.py
# --------------------------------------------------------------------------- #
def test_update_run_ignores_unknown_fields(tmp_db):
    tmp_db.insert_run("r1", state="queued")
    tmp_db.update_run("r1", not_a_column="x")  # no allowed field → early return
    assert tmp_db.get_run("r1").state == "queued"


def test_default_db_url_env_override_and_default(monkeypatch):
    from castiron import db

    monkeypatch.setenv("CASTIRON_DB_URL", "/tmp/explicit.db")
    assert db.default_db_url() == "/tmp/explicit.db"

    monkeypatch.delenv("CASTIRON_DB_URL", raising=False)
    assert db.default_db_url().endswith("castiron.db")


def test_get_db_lazily_creates_default(monkeypatch, tmp_path):
    from castiron import db

    monkeypatch.setenv("CASTIRON_DB_URL", str(tmp_path / "lazy.db"))
    monkeypatch.setattr(db, "_DEFAULT", None)
    created = db.get_db()
    assert isinstance(created, db.Database)
    assert db.get_db() is created  # cached on the second call


# --------------------------------------------------------------------------- #
# gate.py
# --------------------------------------------------------------------------- #
def test_pacing_report_silence_ts():
    from castiron.gate import PacingReport

    rep = PacingReport(target_sec=12.0, duration_sec=12.0, silence_ratio=0.0,
                       lufs=-16.0, emdash_clusters=0, fixed=True)
    assert rep.silence_ts == "00:12"
    # clamped at 41 for very long targets
    long = dataclasses.replace(rep, target_sec=90.0)
    assert long.silence_ts == "00:41"


def _fake_gate_result(quality: dict):
    step = types.SimpleNamespace(metadata={"quality": quality})
    return types.SimpleNamespace(run=types.SimpleNamespace(steps=[step]))


def test_composite_gate_flags_too_hot_loudness():
    from castiron.gate import build_gate_evaluator

    gate = build_gate_evaluator()
    # lufs above the pass band (-14.0) → "too hot"; no silence, no drift
    result = gate.evaluate(_fake_gate_result(
        {"lufs": -10.0, "silence_ratio": 0.0, "duration_drift": 0.0,
         "duration_sec": 10.0, "target_sec": 10.0}))
    assert result.passed is False
    assert "too hot" in result.feedback


def test_composite_gate_requires_an_evaluator():
    from castiron.gate import CompositeGate

    with pytest.raises(ValueError, match="at least one evaluator"):
        CompositeGate()


# --------------------------------------------------------------------------- #
# pipeline.py
# --------------------------------------------------------------------------- #
def test_gate_event_sink_publishes_and_records(tmp_db):
    from castiron.hub import EventHub
    from castiron.pipeline import _gate_event_sink

    tmp_db.insert_run("g1", state="running")
    hub = EventHub()
    emit = _gate_event_sink(tmp_db, "g1", hub, publish=True)
    emit({"type": "gate.iteration.started", "iteration": 0})
    emit({"type": "gate.completed", "passed": True, "iterations": 2})

    types_seen = [e.type for e in tmp_db.list_events("g1")]
    assert "gate.iteration.started" in types_seen
    assert "gate.completed" in types_seen
    gate_stage = next(s for s in tmp_db.list_stages("g1") if s.name == "gate")
    assert gate_stage.state == "succeeded"


def test_run_episode_persists_ladder_retry_event(monkeypatch, tmp_db, tmp_path):
    """The pipeline's on_retry closure persists a durable ladder.retry event."""
    import castiron.pipeline as P

    real_build = P.build_episode_pipeline

    def build_then_signal_retry(*args, **kwargs):
        pipe, sink, backend = real_build(*args, **kwargs)
        kwargs["on_retry"](
            0, types.SimpleNamespace(name="elevenlabs"), 2,
            ProviderError("transient", error_code=ProviderErrorCode.SERVER_ERROR),
        )
        return pipe, sink, backend

    monkeypatch.setattr(P, "build_episode_pipeline", build_then_signal_retry)
    res = P.run_offline_episode(store_root=tmp_path / "s", run_id="retry1", db=tmp_db)
    assert res.ok
    assert any(e.type == "ladder.retry" for e in tmp_db.list_events("retry1"))


def test_run_episode_degrades_when_stream_raises(monkeypatch, tmp_db, tmp_path):
    """An unexpected error in the astream loop is recorded, never crashes the task."""
    import castiron.pipeline as P

    class _BoomPipe:
        async def astream(self, **kwargs):
            raise RuntimeError("stream exploded")
            yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(
        P, "build_episode_pipeline",
        lambda *a, **k: (_BoomPipe(), object(), object()),
    )
    res = P.run_offline_episode(store_root=tmp_path / "s", run_id="boom1", db=tmp_db)
    assert res.state == "failed"
    assert res.ok is False
    assert tmp_db.get_run("boom1").error.startswith("RuntimeError")


# --------------------------------------------------------------------------- #
# app/main.py
# --------------------------------------------------------------------------- #
def test_startup_binds_persistent_db(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setenv("CASTIRON_DB_URL", str(tmp_path / "startup.db"))
    with TestClient(app) as c:  # context manager fires the startup handler
        assert c.get("/healthz").status_code == 200


@pytest.mark.asyncio
async def test_run_background_records_failure(monkeypatch, tmp_db):
    import app.main as main

    async def _boom(**kwargs):
        raise RuntimeError("runner died")

    monkeypatch.setattr(main, "run_episode", _boom)
    tmp_db.insert_run("bg1", state="queued")
    await main._run_background("bg1", main.RunRequest(script="x"))
    assert tmp_db.get_run("bg1").state == "failed"


def test_get_run_returns_state(tmp_db, client):
    tmp_db.insert_run("known", state="completed", voice="narrator")
    tmp_db.upsert_stage("known", "narration", state="succeeded")
    body = client.get("/runs/known").json()
    assert body["run"]["id"] == "known"
    assert body["run"]["state"] == "completed"
    assert any(s["name"] == "narration" for s in body["stages"])


def test_get_run_unknown_404(tmp_db, client):
    assert client.get("/runs/does-not-exist").status_code == 404


def test_console_page_served(client):
    resp = client.get("/console")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_webhook_malformed_payload_returns_400(monkeypatch, tmp_db, client):
    monkeypatch.delenv("WEBHOOK_HMAC_SECRET", raising=False)
    # objectSize is non-numeric → parse_events raises ValueError → HTTP 400
    bad = {"events": [{"eventType": "b2:ObjectCreated:Upload",
                       "objectName": "runs/2026/r/assets/narration.mp3",
                       "objectSize": "not-a-number"}]}
    assert client.post("/webhooks/b2", json=bad).status_code == 400


def test_integrations_verify_offline_missing_store(monkeypatch, tmp_db, client):
    import app.main as main

    absent = dataclasses.replace(main.settings, local_store=Path("/no/such/store/xyz"))
    monkeypatch.setattr(main, "settings", absent)
    payload = client.get("/integrations/verify").json()
    assert payload["object_count"] == 0
    assert payload["sample_keys"] == []


@pytest.mark.asyncio
async def test_sse_stream_times_out_then_completes(tmp_path):
    """A live (non-terminal) run makes the SSE loop hit its poll timeout, then
    emits ``done`` once the run turns terminal — covers the wait_for timeout arm."""
    import asyncio

    import httpx

    from app.main import app
    from castiron.db import Database, set_db

    db = Database(tmp_path / "live.db")
    set_db(db)
    db.insert_run("live1", state="running")  # no background runner → no events

    async def _complete_soon():
        await asyncio.sleep(0.6)  # let the stream loop time out on q.get at least twice
        db.update_run("live1", state="completed")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        completer = asyncio.create_task(_complete_soon())
        names: list[str] = []
        async with client.stream("GET", "/runs/live1/events") as r:
            buf = ""
            async for chunk in r.aiter_text():
                buf += chunk
                while "\n\n" in buf:
                    block, buf = buf.split("\n\n", 1)
                    for line in block.splitlines():
                        if line.startswith("event:"):
                            names.append(line[6:].strip())
                if "done" in names:
                    break
        await completer
    assert names[0] == "open"
    assert names[-1] == "done"
    db.close()
