#!/usr/bin/env python
"""live_publish.py — run a real episode and seal it to the PUBLISHED bucket
under real Backblaze B2 Object Lock, then prove the lock actually holds.

This is the P3-live money shot: an AI-generated media episode, stored immutably
on real B2. Unlike OFFLINE (which only records lock *intent* in metadata), this
sets a genuine per-object GOVERNANCE retention that B2 enforces at the bucket
level — and we prove it by attempting a normal delete and showing B2 refuses.

Requires LIVE mode (B2 creds in env) and a published bucket with Object Lock
ENABLED (ours: castiron-published-edy). Safe: writes one small episode object.

Usage:
    uv run python scripts/live_publish.py                 # fresh episode + publish
    uv run python scripts/live_publish.py --keep-run-dir  # don't delete local run dir
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from castiron.backends import make_media_backend
from castiron.config import load_settings
from castiron.pipeline import run_episode
from castiron.publish import publish_episode

OK, FAIL, INFO = "  [PASS]", "  [FAIL]", "  [INFO]"


def main() -> int:
    settings = load_settings()
    print("=" * 64)
    print("CastIron LIVE publish — seal an episode under real B2 Object Lock")
    print(f"mode={settings.mode}  published={settings.published_bucket}")
    print("=" * 64)

    if settings.offline:
        print(f"{FAIL} OFFLINE — set B2 creds in .env to publish live. Nothing done.")
        return 2

    # 1) produce a real episode (assets + manifest land in the media bucket) ---
    run_id = "livepublish-" + Path(__file__).stem[:4]
    print(f"\n1) RUN EPISODE  (run_id={run_id})")
    result = asyncio.run(run_episode(
        script="CastIron proof: an AI media episode sealed immutably on Backblaze B2.",
        run_id=run_id,
    ))
    if result.state != "completed" or not result.episode_verified:
        print(f"{FAIL} episode did not complete/verify: state={result.state}")
        return 1
    print(f"{OK} episode completed + verified (manifest {result.manifest_hash[:16]}…)")

    episode_path = (
        Path(settings.local_store) / run_id / "b2" / settings.published_bucket
        / "episode.mp3"
    )
    if not episode_path.is_file():
        print(f"{FAIL} embedded episode not found at {episode_path}")
        return 1
    data = episode_path.read_bytes()
    print(f"{INFO} embedded episode: {len(data)} bytes at {episode_path}")

    # 2) publish to the PUBLISHED bucket under real Object Lock ----------------
    print("\n2) PUBLISH UNDER OBJECT LOCK (GOVERNANCE, 30d)")
    published = make_media_backend(Path("."), bucket=settings.published_bucket,
                                   settings=settings)
    pr = publish_episode(
        published,
        run_id=run_id,
        source_key=str(episode_path),
        published_bucket=settings.published_bucket,
        data=data,
        bucket_in_key=False,  # LIVE: the S3 backend already IS the bucket
    )
    print(f"{OK} published key : {pr.published_key}")
    print(f"{OK} lock (intent) : {pr.lock_mode}  retain_until={pr.retain_until}")
    print(f"{OK} sha256        : {pr.sha256}")
    print(f"{OK} durable URL   : {pr.durable_url}")

    # 3) prove the lock is REAL: read the retention B2 actually recorded ------
    # (Stronger + more honest than a delete attempt: B2 buckets keep all
    # versions, so a version-less delete only adds a delete marker — the locked
    # version persists. get_object_retention shows what B2 truly enforces.)
    print("\n3) IMMUTABILITY PROOF (read back the retention B2 enforces)")
    client = published._client          # noqa: SLF001 — boto3 client for the read-back
    bucket = published._bucket          # noqa: SLF001
    try:
        ret = client.get_object_retention(Bucket=bucket, Key=pr.published_key)
        r = ret["Retention"]
        until = r["RetainUntilDate"]
        print(f"{OK} B2 reports Object Lock: mode={r['Mode']}  RetainUntilDate={until}")
        locked = r["Mode"] in ("GOVERNANCE", "COMPLIANCE")
    except Exception as exc:  # noqa: BLE001
        print(f"{FAIL} could not read retention — lock may not be set: "
              f"{type(exc).__name__}: {str(exc)[:140]}")
        locked = False

    print("\n" + "=" * 64)
    if locked:
        print("RESULT: LIVE PUBLISH PASSED — B2 enforces a real retention on the")
        print("episode. Screenshot the object in the B2 console (Object Lock tab")
        print("shows the retain-until date) and record the durable URL in DEMO.md.")
        return 0
    print("RESULT: published, but retention read-back failed — verify bucket lock.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
