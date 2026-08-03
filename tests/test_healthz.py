"""FastAPI skeleton: health + integrations surface."""

from __future__ import annotations


def test_healthz_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "castiron"
    assert body["mode"] == "OFFLINE"
    assert body["genblaze_version"] == "0.4.1"


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "CastIron" in resp.json()["name"]


def test_integrations_verify_offline(client):
    resp = client.get("/integrations/verify")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "OFFLINE"
    assert body["media_bucket"] == "ci-media"
    assert body["published_bucket"] == "ci-published"
    assert "object_count" in body
