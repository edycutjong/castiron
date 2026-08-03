"""P3 · B2 Event Notification receiver + idempotent stage machine (OFFLINE).

Exercises the credential-independent core with SYNTHETIC B2 payloads: HMAC
verification, key→run/stage mapping, the render→mix→verify progression, and
idempotency under duplicate/reordered delivery. The live bucket rule firing is
verified separately at P3 with credentials.
"""

from __future__ import annotations

import json

import pytest

from castiron import webhooks
from castiron.db import Database


@pytest.fixture
def db(tmp_path):
    d = Database(f"sqlite:///{tmp_path}/wh.db")
    d.init()
    d.insert_run("run-abc", state="rendering", script_sha="x")
    yield d
    d.close()


def _event(run="run-abc", stage="narration", *, eid="e1", etype="b2:ObjectCreated:Upload"):
    return {
        "eventId": eid,
        "eventType": etype,
        "bucketName": "ci-media",
        "objectName": f"runs/2026-07-05/{run}/assets/{stage}.mp3",
        "objectSize": 1234,
        "objectVersionId": "v1",
    }


def _body(*events) -> bytes:
    return json.dumps({"events": list(events)}).encode()


# ---- signature -------------------------------------------------------------
def test_hmac_roundtrip_valid():
    body = _body(_event())
    sig = webhooks.sign(body, "s3cr3t")
    assert webhooks.verify_signature(body, sig, "s3cr3t") is True


def test_hmac_rejects_tampered_body():
    sig = webhooks.sign(_body(_event()), "s3cr3t")
    assert webhooks.verify_signature(_body(_event(eid="different")), sig, "s3cr3t") is False


def test_hmac_missing_header_fails_closed_when_secret_set():
    assert webhooks.verify_signature(_body(_event()), None, "s3cr3t") is False


def test_hmac_skipped_when_no_secret():
    # OFFLINE / local dev: unauthenticated but still processed
    assert webhooks.verify_signature(_body(_event()), None, None) is True


# ---- key mapping -----------------------------------------------------------
def test_key_maps_to_run_and_stage():
    assert webhooks.run_stage_from_key("runs/2026-07-05/run-abc/assets/narration.mp3") == (
        "run-abc", "narration",
    )
    assert webhooks.run_stage_from_key("runs/2026-07-05/run-abc/assets/mix.mp3") == (
        "run-abc", "mix",
    )


def test_key_outside_namespace_ignored():
    assert webhooks.run_stage_from_key("logs/whatever.txt") is None


# ---- stage machine ---------------------------------------------------------
def test_all_artifacts_present_advances_to_mix(db):
    m = webhooks.StageMachine(db)
    assert m.handle(webhooks.parse_events(_body(_event(stage="narration", eid="a")))[0]).advanced_to is None
    assert m.handle(webhooks.parse_events(_body(_event(stage="music", eid="b")))[0]).advanced_to is None
    t = m.handle(webhooks.parse_events(_body(_event(stage="cover", eid="c")))[0])
    assert t.advanced_to == "mix"
    assert any(s.name == "mix" and s.state == "running" for s in db.list_stages("run-abc"))


def test_mix_object_advances_to_verify(db):
    m = webhooks.StageMachine(db)
    for stg, eid in [("narration", "a"), ("music", "b"), ("cover", "c")]:
        m.handle(webhooks.parse_events(_body(_event(stage=stg, eid=eid)))[0])
    t = m.handle(webhooks.parse_events(_body(_event(stage="mix", eid="mixed")))[0])
    assert t.advanced_to == "verify"


def test_duplicate_delivery_is_idempotent(db):
    m = webhooks.StageMachine(db)
    ev = webhooks.parse_events(_body(_event(stage="narration", eid="dup")))[0]
    first = m.handle(ev)
    second = m.handle(ev)  # same eventId redelivered
    assert first.duplicate is False
    assert second.duplicate is True
    # exactly one b2.object row recorded despite two deliveries
    objs = [r for r in db.list_events("run-abc")
            if r.type == "b2.object" and json.loads(r.payload_json)["stage"] == "narration"]
    assert len(objs) == 1


def test_reordered_delivery_converges(db):
    # cover arrives first, narration last — still advances to mix exactly once
    m = webhooks.StageMachine(db)
    order = [("cover", "c"), ("music", "b"), ("narration", "a")]
    transitions = [
        m.handle(webhooks.parse_events(_body(_event(stage=s, eid=e)))[0]) for s, e in order
    ]
    advanced = [t.advanced_to for t in transitions if t.advanced_to]
    assert advanced == ["mix"]


def test_non_object_created_ignored(db):
    m = webhooks.StageMachine(db)
    ev = webhooks.parse_events(_body(_event(etype="b2:ObjectDeleted")))[0]
    assert m.handle(ev).advanced_to is None


def test_handle_delivery_bad_signature_raises(db):
    body = _body(_event())
    with pytest.raises(PermissionError):
        webhooks.handle_delivery(db, body, "sha256=wrong", "s3cr3t")


def test_handle_delivery_summary(db):
    body = _body(_event(stage="narration", eid="a"), _event(stage="music", eid="b"))
    out = webhooks.handle_delivery(db, body, webhooks.sign(body, "k"), "k")
    assert out["processed"] == 2
    assert out["duplicates"] == 0


# ---- HTTP route (the surface live B2 actually hits) ------------------------
def test_webhook_route_accepts_valid_delivery(client, monkeypatch):
    from castiron.db import get_db
    monkeypatch.delenv("WEBHOOK_HMAC_SECRET", raising=False)
    get_db().insert_run("run-route", state="rendering", script_sha="x")
    body = _body(_event(run="run-route", stage="narration", eid="route-ok"))
    resp = client.post("/webhooks/b2", content=body)
    assert resp.status_code == 200
    assert resp.json()["processed"] == 1


def test_webhook_route_ignores_unknown_run(client, monkeypatch):
    monkeypatch.delenv("WEBHOOK_HMAC_SECRET", raising=False)
    body = _body(_event(run="nobody", stage="narration", eid="ghost"))
    resp = client.post("/webhooks/b2", content=body)
    assert resp.status_code == 200
    assert resp.json()["advanced"] == []


def test_webhook_route_rejects_bad_signature(client, monkeypatch):
    monkeypatch.setenv("WEBHOOK_HMAC_SECRET", "topsecret")
    body = _body(_event(eid="route-bad"))
    resp = client.post(
        "/webhooks/b2", content=body,
        headers={webhooks.SIGNATURE_HEADER: "sha256=nope"},
    )
    assert resp.status_code == 401


# ---- defensive stage-machine edges (handle() red-paths) --------------------
def test_handle_unknown_run_is_ignored_not_500(db):
    """A delivery for a run this node doesn't own (foreign bucket / post-cleanup
    replay) is a no-op, never a crash."""
    m = webhooks.StageMachine(db)
    ev = webhooks.parse_events(_body(_event(run="ghost-run", eid="g1")))[0]
    t = m.handle(ev)
    assert t.advanced_to is None
    assert "unknown run" in t.reason


def test_handle_key_outside_namespace_is_ignored(db):
    """An ObjectCreated for a key outside runs/.../assets/ maps to nothing."""
    m = webhooks.StageMachine(db)
    ev = webhooks.B2Event(
        event_id="k1", event_type="b2:ObjectCreated:Upload", bucket="ci-media",
        object_name="logs/2026/system.log", object_size=1, version_id="v1",
    )
    t = m.handle(ev)
    assert t.advanced_to is None
    assert "outside run namespace" in t.reason


def test_enter_mix_is_idempotent_under_reprocessing(db):
    """After all three artifacts land, MIX is entered once. A later (non-duplicate)
    re-delivery of an artifact must NOT enter MIX a second time."""
    m = webhooks.StageMachine(db)
    for stg, eid in [("narration", "a"), ("music", "b"), ("cover", "c")]:
        m.handle(webhooks.parse_events(_body(_event(stage=stg, eid=eid)))[0])
    # a genuinely new delivery (fresh eventId) for an already-present artifact:
    # all three still present, but MIX is already running → no re-enter.
    t = m.handle(webhooks.parse_events(_body(_event(stage="cover", eid="c-again")))[0])
    assert t.advanced_to is None
    assert "already entered" in t.reason
    mix_stages = [s for s in db.list_stages("run-abc") if s.name == "mix"]
    assert len(mix_stages) == 1
