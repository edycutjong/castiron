"""Publish stage (P3) — seal the finished episode to the published bucket.

The last stage of the event-driven machine: once VERIFY passes, the mixed
episode is copied to the ``ci-published`` bucket under Object Lock (governance,
30-day retention) and served by a durable URL.

CREDENTIAL-INDEPENDENT core: the copy, the lock-intent recording, and the
key layout are exercised OFFLINE against ``LocalDirBackend``. The LIVE swap
(SDKCHK #5, verified surface) is a one-liner — the real sink is
``ObjectStorageSink(manifest_lock=ObjectLockConfig(retain_until=…,
mode="GOVERNANCE"))`` and the backend ``put(object_lock=…)``; OFFLINE records
the same intent in object metadata so the ops dashboard and tests can assert it.
Object Lock genuinely enforcing immutability is a bucket-level guarantee only
real B2 can make — asserted live at P3, not fakeable OFFLINE (stated honestly).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from genblaze_core import ObjectLockConfig

DEFAULT_RETAIN_DAYS = 30
DEFAULT_LOCK_MODE = "GOVERNANCE"  # ObjectLockConfig.mode ∈ {GOVERNANCE, COMPLIANCE}


@dataclass(frozen=True)
class PublishResult:
    run_id: str
    published_key: str
    bucket: str
    retain_until: str
    lock_mode: str
    durable_url: str
    sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "published_key": self.published_key,
            "bucket": self.bucket,
            "retain_until": self.retain_until,
            "lock_mode": self.lock_mode,
            "durable_url": self.durable_url,
            "sha256": self.sha256,
        }


def object_lock_metadata(retain_until: str, mode: str) -> dict[str, str]:
    """The X-Bz-Info tags recording the lock intent (LIVE sets a real lock)."""
    return {
        "object-lock-mode": mode,
        "object-lock-retain-until": retain_until,
    }


def publish_episode(
    backend: Any,
    *,
    run_id: str,
    source_key: str,
    published_bucket: str = "ci-published",
    retain_days: int = DEFAULT_RETAIN_DAYS,
    mode: str = DEFAULT_LOCK_MODE,
    extra_metadata: dict[str, str] | None = None,
    data: bytes | None = None,
    bucket_in_key: bool = True,
) -> PublishResult:
    """Copy the verified episode to the published bucket under Object Lock.

    Idempotent: re-publishing the same run rewrites the identical key (the
    content-addressed sha means byte-identical inputs land identically). Raises
    FileNotFoundError if the source episode isn't present.

    OFFLINE (same-backend) reads the source via ``backend.get(source_key)``.
    LIVE crosses backends — the embedded episode is a local file and the
    destination is the separate published B2 bucket — so callers pass the bytes
    directly via ``data`` (``source_key`` is retained for provenance/logging).
    """
    import hashlib

    if data is None:
        data = backend.get(source_key)  # raises FileNotFoundError if absent
    sha = hashlib.sha256(data).hexdigest()
    retain_dt = datetime.now(UTC) + timedelta(days=retain_days)
    retain_until = retain_dt.isoformat()
    # OFFLINE: one LocalDirBackend simulates buckets as subdirs, so the bucket
    # name is part of the key. LIVE: the S3 backend IS the bucket — prefixing it
    # again would double it in the object path — so key = {run_id}/episode.mp3.
    published_key = (
        f"{published_bucket}/{run_id}/episode.mp3" if bucket_in_key
        else f"{run_id}/episode.mp3"
    )

    metadata = {
        "run-id": run_id,
        "source-sha256": sha,
        **object_lock_metadata(retain_until, mode),
        **(extra_metadata or {}),
    }
    # LIVE: backend.put(object_lock=ObjectLockConfig(...)) sets a real B2
    # per-object retention (bucket must have Object Lock enabled — ours does).
    # OFFLINE: LocalDirBackend records the same intent in its metadata sidecar.
    # The metadata tags above are the human/dashboard-readable mirror of the lock.
    backend.put(
        published_key,
        data,
        content_type="audio/mpeg",
        metadata=metadata,
        object_lock=ObjectLockConfig(retain_until=retain_dt, mode=mode),
    )
    durable_url = backend.get_durable_url(published_key)
    return PublishResult(
        run_id=run_id,
        published_key=published_key,
        bucket=published_bucket,
        retain_until=retain_until,
        lock_mode=mode,
        durable_url=durable_url,
        sha256=sha,
    )
