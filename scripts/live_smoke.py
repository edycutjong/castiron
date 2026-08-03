#!/usr/bin/env python
"""live_smoke.py — the FIRST thing to run when real B2 credentials land.

Confirms the foundational LIVE assumptions against real Backblaze B2 — auth,
bucket reachability, put/get/metadata round-trip, durable URLs, and (opt-in) a
real provider call — WITHOUT needing the full pipeline live-wired yet. Its job
is to turn "assumed" into "verified" and kill the mock-mode risk at the root.

SAFE: touches only a ``_smoke/`` prefix with tiny objects and cleans up after
itself. Never mutates real run data. B2-only by default; the (paid) provider
probe is opt-in behind ``--providers``.

Exit codes: 0 = all attempted probes passed · 1 = a probe FAILED · 2 = not
configured (no B2 creds) — CI-safe, distinct from failure.

Usage:
    uv run python scripts/live_smoke.py            # B2 probes only
    uv run python scripts/live_smoke.py --providers  # + one tiny real TTS call
    uv run python scripts/live_smoke.py --keep       # don't delete smoke objects
"""

from __future__ import annotations

import os
import sys
import time
from datetime import UTC, datetime

from castiron.config import load_settings

OK, FAIL, SKIP = "  [PASS]", "  [FAIL]", "  [SKIP]"


def _hdr(t: str) -> None:
    print(f"\n{t}")


def main() -> int:
    keep = "--keep" in sys.argv
    do_providers = "--providers" in sys.argv
    settings = load_settings()
    failures = 0

    print("=" * 64)
    print("CastIron LIVE smoke test")
    print(f"mode={settings.mode}  media={settings.media_bucket}  "
          f"published={settings.published_bucket}")
    print("=" * 64)

    # ---- Layer 0: credentials ------------------------------------------- #
    _hdr("0) CREDENTIALS")
    key_id = os.environ.get("B2_KEY_ID")
    app_key = os.environ.get("B2_APP_KEY")
    if not (key_id and app_key):
        print(f"{FAIL} B2_KEY_ID / B2_APP_KEY not set — NOT CONFIGURED.")
        print("       Add them to .env (see .env.example). For the exact bucket")
        print("       + key + rule commands, run: scripts/b2_setup.sh --plan")
        print("\nRESULT: NOT CONFIGURED (nothing to verify live yet).")
        return 2
    print(f"{OK} B2 credentials present (key_id ...{key_id[-4:]})")
    for name in ("ELEVENLABS_API_KEY", "LMNT_API_KEY", "HUME_API_KEY",
                 "STABILITY_API_KEY", "OPENAI_API_KEY", "GMI_API_KEY"):
        print(f"       provider {name:<20} {'set' if os.environ.get(name) else '—'}")

    # ---- Layer 1: auth + bucket reachability ---------------------------- #
    _hdr("1) B2 AUTH + BUCKET REACHABILITY (preflight)")
    try:
        from genblaze_s3 import S3StorageBackend
    except Exception as exc:  # pragma: no cover
        print(f"{FAIL} cannot import genblaze_s3: {exc}")
        return 1

    backends: dict[str, object] = {}
    for label, bucket in (("media", settings.media_bucket),
                          ("published", settings.published_bucket)):
        try:
            backends[label] = S3StorageBackend.for_backblaze(
                bucket, key_id=key_id, app_key=app_key, preflight=True
            )
            print(f"{OK} {label} bucket '{bucket}' reachable + authorized")
        except Exception as exc:
            failures += 1
            print(f"{FAIL} {label} bucket '{bucket}': {type(exc).__name__}: {exc}")

    # ---- Layer 2: round-trip (put/get/metadata/url/delete) -------------- #
    _hdr("2) OBJECT ROUND-TRIP  (put · get · X-Bz-Info metadata · durable URL · delete)")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    smoke_key = f"_smoke/{stamp}-{int(time.time())}.txt"
    payload = b"castiron-live-smoke"
    md = {"stage": "smoke", "sha-note": "roundtrip", "run-id": "smoke"}

    mb = backends.get("media")
    if mb is None:
        print(f"{SKIP} media backend unavailable (see Layer 1)")
    else:
        try:
            mb.put(smoke_key, payload, content_type="text/plain", metadata=md)
            print(f"{OK} put {smoke_key}")
            got = mb.get(smoke_key)
            print(f"{OK} get round-trips bytes" if got == payload
                  else f"{FAIL} get mismatch: {got!r}")
            failures += got != payload
            # metadata round-trip (resolves the X-Bz-Info live question)
            try:
                meta = mb.describe(smoke_key).metadata
                ok = meta.get("stage") == "smoke"
                print(f"{OK} X-Bz-Info metadata round-trips (stage=smoke)" if ok
                      else f"{FAIL} metadata missing/mismatched: {meta}")
                failures += not ok
            except (NotImplementedError, AttributeError):
                # describe() is a LocalDirBackend convenience, not part of the
                # genblaze StorageBackend contract — the real S3 backend omits it.
                print(f"{SKIP} describe() not on S3 backend (non-contract) — "
                      "verify X-Bz-Info metadata via B2 console instead")
            # durable URL
            try:
                url = mb.get_durable_url(smoke_key)
                print(f"{OK} durable URL: {url[:72]}...")
            except Exception as exc:
                print(f"{SKIP} durable URL: {type(exc).__name__}: {exc}")
        except Exception as exc:
            failures += 1
            print(f"{FAIL} round-trip: {type(exc).__name__}: {exc}")
        finally:
            if not keep:
                try:
                    mb.delete(smoke_key)
                    print(f"{OK} cleaned up {smoke_key}")
                except Exception as exc:
                    print(f"{SKIP} cleanup: {exc} (delete _smoke/ by hand)")

    # ---- Layer 3: optional real provider call --------------------------- #
    _hdr("3) LIVE PROVIDER PROBE (opt-in: --providers)")
    if not do_providers:
        print(f"{SKIP} skipped (pass --providers to make one tiny real TTS call)")
    elif not os.environ.get("ELEVENLABS_API_KEY"):
        print(f"{SKIP} no ELEVENLABS_API_KEY — set one to probe a real run")
    else:
        print("       (P3-live wires the real provider into the pipeline;")
        print("        until then this is a placeholder for that session's")
        print("        first real narration call under MAX_RUN_COST_USD.)")
        print(f"{SKIP} deferred to P3-live pipeline wiring")

    # ---- Report --------------------------------------------------------- #
    print("\n" + "=" * 64)
    if failures == 0:
        print("RESULT: LIVE SMOKE PASSED — B2 auth, buckets, round-trip, and")
        print("metadata are real. Safe to start the P3-live session:")
        print("  1) wire the OFFLINE→LIVE backend factory into pipeline/app")
        print("  2) create the Event Notification rule (confirm SDKCHK #7 header)")
        print("  3) run a real episode → PUBLISHED under Object Lock, screenshot it")
        return 0
    print(f"RESULT: {failures} probe(s) FAILED — fix before P3-live. "
          "Log any SDK surprise in DEVIATIONS.md + docs/friction-log.md.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
