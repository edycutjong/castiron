"""LocalDirBackend — an on-disk :class:`genblaze_core.storage.base.StorageBackend`.

This is CastIron's OFFLINE storage plane and a genblaze extension-point proof
(we implement the documented ``StorageBackend`` interface rather than consume a
prebuilt one). It backs ``OFFLINE=1``: no network, no credentials, always green.

The abstract surface we satisfy (verified by introspection at build, SDKCHK #8):

    put(key, data, *, content_type, metadata, extra_args) -> str
    get(key) -> bytes
    exists(key) -> bool
    delete(key) -> None
    get_url(key, *, expires_in=3600) -> str      # presigned analogue (time-boxed)
    get_durable_url(key) -> str                  # permanent analogue
    list(prefix, *, max_keys, continuation_token) -> ListPage

Object metadata (the S3/B2 ``X-Bz-Info`` tags CastIron writes: stage, rung,
score, plus content_type and any ``extra_args`` such as SSE/object-lock hints)
is persisted in a sibling ``.castiron-meta/`` tree so the object key space stays
clean and ``/integrations/verify`` can surface tags offline.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from genblaze_core import ObjectLockConfig
from genblaze_core.storage.base import StorageBackend
from genblaze_core.storage.types import FileEntry, ListPage, ObjectMetadata

from castiron.config import Settings
from castiron.config import settings as _default_settings

_META_DIR = ".castiron-meta"


def _as_bytes(data: bytes | BinaryIO) -> bytes:
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    if hasattr(data, "read"):
        return data.read()
    raise TypeError(f"unsupported data type for put(): {type(data)!r}")


class LocalDirBackend(StorageBackend):
    """Filesystem-backed StorageBackend rooted at ``root``.

    Keys map to paths under ``root``. Safe against path traversal (keys are
    normalised and confined to the root).
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / _META_DIR).mkdir(parents=True, exist_ok=True)

    # -- key <-> path plumbing -------------------------------------------------

    def _path(self, key: str) -> Path:
        key = key.lstrip("/")
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root) + os.sep):
            raise ValueError(f"key escapes storage root: {key!r}")
        return p

    def _meta_path(self, key: str) -> Path:
        return self.root / _META_DIR / (key.lstrip("/") + ".json")

    def _is_meta(self, p: Path) -> bool:
        return _META_DIR in p.relative_to(self.root).parts

    # -- StorageBackend interface ---------------------------------------------

    def put(
        self,
        key: str,
        data: bytes | BinaryIO,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
        extra_args: dict[str, Any] | None = None,
        object_lock: ObjectLockConfig | None = None,
    ) -> str:
        raw = _as_bytes(data)
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # atomic-ish write
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(raw)
        os.replace(tmp, path)

        # Object Lock parity with S3StorageBackend: OFFLINE can't enforce
        # immutability (a real-B2 bucket-level guarantee) but records the intent
        # so the ops dashboard + tests observe the same lock the LIVE put sets.
        lock_meta = (
            {
                "object-lock-mode": object_lock.mode,
                "object-lock-retain-until": object_lock.retain_until.isoformat(),
            }
            if object_lock is not None
            else {}
        )
        mpath = self._meta_path(key)
        mpath.parent.mkdir(parents=True, exist_ok=True)
        mpath.write_text(
            json.dumps(
                {
                    "content_type": content_type,
                    "metadata": {**(metadata or {}), **lock_meta},
                    "extra_args": {k: str(v) for k, v in (extra_args or {}).items()},
                    "size": len(raw),
                    "etag": hashlib.md5(raw).hexdigest(),  # noqa: S324 (S3 ETag semantics)
                    "last_modified": datetime.now(UTC).isoformat(),
                },
                indent=2,
            )
        )
        return key

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(f"no object at key {key!r}")
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()
        mpath = self._meta_path(key)
        if mpath.is_file():
            mpath.unlink()

    def get_url(self, key: str, *, expires_in: int = 3600) -> str:
        # OFFLINE presigned analogue: a file URI carrying the expiry window so
        # the time-boxed-delivery contract (URLPolicy) is observable in tests.
        return f"{self._path(key).as_uri()}#presigned&expires_in={expires_in}"

    def get_durable_url(self, key: str) -> str:
        return self._path(key).as_uri()

    def list(
        self,
        prefix: str = "",
        *,
        max_keys: int = 1000,
        continuation_token: str | None = None,
    ) -> ListPage:
        keys: list[str] = []
        for dirpath, _dirs, files in os.walk(self.root):
            for name in files:
                p = Path(dirpath) / name
                if self._is_meta(p) or p.suffix == ".tmp":
                    continue
                rel = p.relative_to(self.root).as_posix()
                if rel.startswith(prefix):
                    keys.append(rel)
        keys.sort()
        if continuation_token:
            keys = [k for k in keys if k > continuation_token]
        page = keys[:max_keys]
        next_token = page[-1] if len(keys) > max_keys else None
        entries = tuple(self._file_entry(k) for k in page)
        return ListPage(entries=entries, next_token=next_token)

    # -- extras (not part of the ABC; used by the ops panel / tests) -----------

    def _file_entry(self, key: str) -> FileEntry:
        path = self._path(key)
        st = path.stat()
        meta = self._read_meta(key)
        return FileEntry(
            key=key,
            size=st.st_size,
            last_modified=datetime.fromtimestamp(st.st_mtime, tz=UTC),
            etag=meta.get("etag", ""),
        )

    def _read_meta(self, key: str) -> dict[str, Any]:
        mpath = self._meta_path(key)
        if mpath.is_file():
            return json.loads(mpath.read_text())
        return {}

    def describe(self, key: str) -> ObjectMetadata:
        """Return object metadata (tags included) for the ops dashboard."""
        path = self._path(key)
        st = path.stat()
        meta = self._read_meta(key)
        return ObjectMetadata(
            key=key,
            size=st.st_size,
            last_modified=datetime.fromtimestamp(st.st_mtime, tz=UTC),
            etag=meta.get("etag", ""),
            content_type=meta.get("content_type"),
            metadata=meta.get("metadata", {}),
        )


# --------------------------------------------------------------------------- #
# Mode-aware backend factory (OFFLINE ↔ LIVE)
# --------------------------------------------------------------------------- #
def make_media_backend(
    base: Path, *, bucket: str | None = None, settings: Settings | None = None
) -> StorageBackend:
    """Return the media StorageBackend for the active mode.

    OFFLINE (no B2 creds, or ``OFFLINE=1``) → on-disk :class:`LocalDirBackend`
    rooted under ``base`` — the always-green demo-day fallback. LIVE (creds
    present) → the genblaze ``S3StorageBackend`` bound to the real B2 media
    bucket. ``genblaze_s3`` is imported lazily so the OFFLINE path keeps its
    zero-S3-dependency import guarantee.
    """
    st = settings or _default_settings
    bucket = bucket or st.media_bucket
    if st.offline:
        return LocalDirBackend(base / "b2" / bucket)
    from genblaze_s3 import S3StorageBackend

    return S3StorageBackend.for_backblaze(
        bucket,
        key_id=os.environ["B2_KEY_ID"],
        app_key=os.environ["B2_APP_KEY"],
        preflight=False,
    )
