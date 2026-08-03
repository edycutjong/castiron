"""LocalDirBackend — the OFFLINE StorageBackend (SDKCHK #8 extension proof)."""

from __future__ import annotations

import pytest

from castiron.backends import LocalDirBackend


def test_put_get_roundtrip(store):
    be = LocalDirBackend(store)
    key = be.put("runs/a/x.bin", b"hello", content_type="application/octet-stream")
    assert key == "runs/a/x.bin"
    assert be.get("runs/a/x.bin") == b"hello"
    assert be.exists("runs/a/x.bin")


def test_put_accepts_binaryio(store, tmp_path):
    be = LocalDirBackend(store)
    src = tmp_path / "src.bin"
    src.write_bytes(b"streamed")
    with src.open("rb") as fh:
        be.put("k/streamed.bin", fh)
    assert be.get("k/streamed.bin") == b"streamed"


def test_get_missing_raises(store):
    be = LocalDirBackend(store)
    with pytest.raises(FileNotFoundError):
        be.get("nope")


def test_delete(store):
    be = LocalDirBackend(store)
    be.put("d/x", b"1")
    assert be.exists("d/x")
    be.delete("d/x")
    assert not be.exists("d/x")
    be.delete("d/x")  # idempotent


def test_list_prefix_and_excludes_meta(store):
    be = LocalDirBackend(store)
    be.put("runs/1/a.bin", b"a")
    be.put("runs/2/b.bin", b"b")
    be.put("other/c.bin", b"c")
    keys = [e.key for e in be.list(prefix="runs/").entries]
    assert keys == ["runs/1/a.bin", "runs/2/b.bin"]
    # metadata sidecars never leak into listings
    all_keys = [e.key for e in be.list().entries]
    assert not any(".castiron-meta" in k for k in all_keys)


def test_list_pagination(store):
    be = LocalDirBackend(store)
    for i in range(5):
        be.put(f"p/{i}.bin", b"x")
    page = be.list(prefix="p/", max_keys=2)
    assert len(page.entries) == 2
    assert page.next_token is not None
    page2 = be.list(prefix="p/", max_keys=2, continuation_token=page.next_token)
    assert len(page2.entries) == 2


def test_urls(store):
    be = LocalDirBackend(store)
    be.put("u/x.bin", b"x")
    presigned = be.get_url("u/x.bin", expires_in=900)
    assert presigned.startswith("file://")
    assert "expires_in=900" in presigned
    durable = be.get_durable_url("u/x.bin")
    assert durable.startswith("file://") and "expires_in" not in durable


def test_describe_metadata_roundtrip(store):
    be = LocalDirBackend(store)
    be.put("m/x.bin", b"x", content_type="audio/mpeg",
           metadata={"stage": "tts", "rung": "2"})
    meta = be.describe("m/x.bin")
    assert meta.content_type == "audio/mpeg"
    assert meta.metadata["stage"] == "tts"
    assert meta.metadata["rung"] == "2"
    assert meta.size == 1


def test_path_traversal_guarded(store):
    be = LocalDirBackend(store)
    with pytest.raises(ValueError):
        be.put("../escape.bin", b"x")


def test_is_a_real_storagebackend():
    from genblaze_core.storage.base import StorageBackend

    assert issubclass(LocalDirBackend, StorageBackend)
    # all abstract methods are implemented -> instantiable
    assert not getattr(LocalDirBackend, "__abstractmethods__", set())


def test_put_rejects_unsupported_data_type(store):
    be = LocalDirBackend(store)
    with pytest.raises(TypeError):
        be.put("bad/x.bin", 12345)  # not bytes and not a stream


def test_describe_without_sidecar_returns_empty_meta(store):
    """An object written outside put() (no metadata sidecar) still describes
    cleanly with empty tags rather than raising."""
    be = LocalDirBackend(store)
    orphan = be.root / "orphan.bin"
    orphan.write_bytes(b"x")
    md = be.describe("orphan.bin")
    assert md.metadata == {}
    assert md.etag == ""
    assert md.content_type is None
