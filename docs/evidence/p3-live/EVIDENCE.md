# P3-LIVE evidence — real Backblaze B2 (2026-07-26)

CastIron proven against **real** Backblaze B2 (region `us-east-005`), not mocks.
Everything here is reproducible with credentials in `.env` (gitignored).

## Buckets
| Bucket | Type | Object Lock | Role |
|---|---|---|---|
| `castiron-media-edy` | Private | disabled | run assets + manifests (`runs/{date}/{run}/…`) |
| `castiron-published-edy` | Private | **ENABLED** | sealed episodes under GOVERNANCE retention |

Endpoint: `s3.us-east-005.backblazeb2.com` · App key `castiron-live` (All buckets, R/W).

## 1 · Live smoke — `scripts/live_smoke.py`
`RESULT: LIVE SMOKE PASSED` — B2 auth, both buckets reachable/authorized,
object round-trip (put · get · durable URL · delete) all green.

## 2 · Real episode on B2 — `run_episode(run_id="livedemo03")`
`state=completed`, `manifest_verified=True`, `episode_verified=True`, inline
manifest embed. 4 objects landed under `runs/2026-07-26/…` (manifest.json + 2
audio + cover.png). Storage plane is LIVE; generative providers still synth
stand-ins (real TTS ladder pending ELEVENLABS/LMNT/HUME keys).

## 3 · Immutable publish under Object Lock — `scripts/live_publish.py`
```
2) PUBLISH UNDER OBJECT LOCK (GOVERNANCE, 30d)
  [PASS] published key : livepublish-live/episode.mp3
  [PASS] lock (intent) : GOVERNANCE  retain_until=2026-08-25T03:44:14+00:00
  [PASS] sha256        : 73a989887a8492ae022d07fa5a9f28d7323200f302b1abde702143fdc5bfff5f
  [PASS] durable URL   : https://s3.us-east-005.backblazeb2.com/castiron-published-edy/livepublish-live/episode.mp3
3) IMMUTABILITY PROOF (read back the retention B2 enforces)
  [PASS] B2 reports Object Lock: mode=GOVERNANCE  RetainUntilDate=2026-08-25 03:44:14+00:00
```
The immutability is proven by reading back what B2 **actually enforces**
(`get_object_retention`) — not a delete attempt (B2 keeps all versions, so a
version-less delete only adds a delete marker while the locked version persists).

## 4 · SDKCHK #7 RESOLVED — Event Notification signature header
Confirmed against Backblaze's Event Notifications reference guide:
- **Header:** `X-Bz-Event-Notification-Signature` (HTTP header names are
  case-insensitive; the ASGI layer lowercases them — our default matches).
- **Value:** `v1=<lowercase hex HMAC-SHA256 over the raw body>`.
`castiron/webhooks.verify_signature` splits on `=` so it accepts the real `v1=`
prefix; `sign()` now mirrors B2's `v1=` exactly. A full live delivery round-trip
additionally needs the public receiver (post-deploy) + the `b2 bucket
notification-rule create` command printed by `scripts/b2_setup.sh --plan`.

## Reproduce
```bash
set -a && . ./.env && set +a
uv run python scripts/live_smoke.py       # B2 auth + round-trip
uv run python scripts/live_publish.py     # episode → Object-Lock publish + retention read-back
OFFLINE=1 uv run python -m pytest         # 112 passed (OFFLINE stays green)
```
