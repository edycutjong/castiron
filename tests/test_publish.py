"""P3 · publish stage — seal to ci-published under Object Lock (OFFLINE core).

Asserts the copy, the lock-intent metadata, the durable URL, and idempotent
re-publish against LocalDirBackend. Object Lock actually enforcing immutability
is a live-B2 guarantee verified at P3 with credentials (not fakeable here).
"""

from __future__ import annotations

import pytest

from castiron.backends import LocalDirBackend
from castiron.publish import object_lock_metadata, publish_episode


@pytest.fixture
def backend(tmp_path):
    b = LocalDirBackend(tmp_path / "store")
    b.put("ci-media/runs/r1/assets/mix.mp3", b"ID3-episode-bytes",
          content_type="audio/mpeg", metadata={"stage": "mix"})
    return b


def test_publish_copies_to_published_bucket(backend):
    r = publish_episode(backend, run_id="r1",
                        source_key="ci-media/runs/r1/assets/mix.mp3")
    assert r.published_key == "ci-published/r1/episode.mp3"
    assert backend.exists(r.published_key)
    assert backend.get(r.published_key) == b"ID3-episode-bytes"


def test_publish_records_object_lock_intent(backend):
    r = publish_episode(backend, run_id="r1",
                        source_key="ci-media/runs/r1/assets/mix.mp3",
                        retain_days=30, mode="GOVERNANCE")
    assert r.lock_mode == "GOVERNANCE"
    meta = backend.describe(r.published_key).metadata
    assert meta["object-lock-mode"] == "GOVERNANCE"
    assert meta["object-lock-retain-until"] == r.retain_until
    assert meta["source-sha256"] == r.sha256


def test_publish_returns_durable_url(backend):
    r = publish_episode(backend, run_id="r1",
                        source_key="ci-media/runs/r1/assets/mix.mp3")
    assert r.durable_url and r.published_key in r.durable_url


def test_publish_idempotent_rewrites_same_key(backend):
    a = publish_episode(backend, run_id="r1",
                        source_key="ci-media/runs/r1/assets/mix.mp3")
    b = publish_episode(backend, run_id="r1",
                        source_key="ci-media/runs/r1/assets/mix.mp3")
    assert a.published_key == b.published_key
    assert a.sha256 == b.sha256


def test_publish_missing_source_raises(backend):
    with pytest.raises(FileNotFoundError):
        publish_episode(backend, run_id="r1", source_key="ci-media/runs/r1/assets/nope.mp3")


def test_object_lock_metadata_shape():
    m = object_lock_metadata("2026-08-04T00:00:00+00:00", "COMPLIANCE")
    assert m == {
        "object-lock-mode": "COMPLIANCE",
        "object-lock-retain-until": "2026-08-04T00:00:00+00:00",
    }


def test_publish_result_as_dict_roundtrips(backend):
    r = publish_episode(backend, run_id="r1",
                        source_key="ci-media/runs/r1/assets/mix.mp3")
    d = r.as_dict()
    assert d == {
        "run_id": r.run_id,
        "published_key": r.published_key,
        "bucket": r.bucket,
        "retain_until": r.retain_until,
        "lock_mode": r.lock_mode,
        "durable_url": r.durable_url,
        "sha256": r.sha256,
    }


def test_publish_live_key_layout_omits_bucket_prefix(backend):
    """LIVE crosses backends: the S3 sink IS the bucket, so the key must NOT be
    prefixed with the bucket name (that would double it in the object path). The
    ``bucket_in_key=False`` + explicit ``data`` path is the LIVE-shaped call."""
    r = publish_episode(
        backend, run_id="r1", source_key="ci-media/runs/r1/assets/mix.mp3",
        data=b"ID3-episode-bytes", bucket_in_key=False,
    )
    assert r.published_key == "r1/episode.mp3"      # no ci-published/ prefix
    assert r.bucket == "ci-published"               # bucket still recorded
    # object-lock intent is still recorded on the written object
    meta = backend.describe(r.published_key).metadata
    assert meta["object-lock-mode"] == "GOVERNANCE"
