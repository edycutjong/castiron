# Demo & Benchmarks — CastIron

## The 30-second demo

**Hero query:** *Kill the primary TTS provider mid-render — does the episode still ship, hash-verified and published?*

- **Input:** the `space_update` script (`seed/episodes.json`) with the primary voice
  provider forced down — `chaos="tts"` (in the UI: flip the **Chaos** toggle to *TTS outage*).
- **What happens:** the narration ladder catches the outage on rung 0 (`elevenlabs`),
  steps down to rung 1 (`lmnt`), and the 3-stage fan-out (narration · music · cover)
  completes. The manifest is read back with `verify=True`, embedded inline into
  `episode.mp3`, and `verify_file()` returns **True**. The live SSE rail shows the rung
  step in real time.
- **Expected output:** a playable `episode.mp3` whose in-file manifest verifies, with the
  manifest recording the **actual** rung used (`lmnt-blizzard`, `fallback_rung=1`) — not
  the requested one. **Zero dropped episodes.**

## Headline number

> **96 / 96 episodes shipped hash-verified across healthy + forced-outage runs — 0 dropped.**

The primary TTS provider is killed on *every* failover trial; the cross-provider ladder
still lands a verified, publish-ready episode every time. Failover adds no measurable
latency: **p50 ≈ 120 ms, p95 ≈ 134 ms** end-to-end (render + manifest verify + in-file
embed), OFFLINE, on the reference machine (Apple Silicon, Python 3.11, ffmpeg via brew).

## Reproduce

```bash
git clone <repo> && cd castiron/build
uv sync                       # installs genblaze==0.4.1 + deps (needs network once)
# ffmpeg must be on PATH (brew install ffmpeg / apt-get install -y ffmpeg)
OFFLINE=1 .venv/bin/python bench.py
```

Zero config, no API keys, no B2 credentials — `OFFLINE=1` uses mock providers +
`LocalDirBackend`, the same always-green path the app falls back to on demo day. The
script exits **non-zero** if any correctness gate fails. Expected tail:

```
HEADLINE: 96/96 episodes shipped hash-verified across healthy + forced-outage runs — 0 dropped.
ALL GREEN — 0 dropped episodes
```

> Note: run tests/bench with `.venv/bin/python` (not `uv run`) offline — `uv run`
> re-syncs and can drop the pre-installed `genblaze` wheels when the network is absent.

## Full results

| Scenario | n | p50 | p95 | Correctness gate |
|---|---|---|---|---|
| Healthy (provider up) | 48 | ~119 ms | ~126 ms | every episode ships verified (48/48) |
| **Failover** (primary TTS killed) | 48 | ~120 ms | ~134 ms | rung steps down **and** still ships (48/48) |
| Tamper (1 byte of provenance edited) | 1 | — | — | `verify()` flips to **False** |
| Budget (projected spend over cap) | 1 | — | — | hard-abort **before** spend (`BUDGET_ABORT`) |

`n = 6 seed episodes × 8 repeats` per render scenario; 2 warm-up runs discarded.
Correctness is the point — latency is secondary and reported only for honesty.

## Methodology & limitations

- **Seed:** fixed (`SEED=42`); dataset is the **operator-seeded** `seed/episodes.json`
  (6 real-shaped podcast scripts). It is realistic background material, **not** the
  capability being judged — the engine that renders/verifies/publishes them is.
- **Latency is OFFLINE orchestration only.** Mock providers stand in for real TTS/music/
  image vendors, so the numbers measure fan-out + manifest verify + ID3 embed — **not**
  real-vendor synthesis latency, which is provider-bound and excluded. We do **not**
  headline a speed claim; the headline is the reliability figure.
- **Single machine, single process.** No distributed/throughput claim is made.
- **LIVE parity:** real B2 storage, Object Lock, and a real-vendor run are proven
  separately — see `scripts/live_smoke.py`, `scripts/live_publish.py`, and
  `docs/evidence/p3-live/`. The OFFLINE benchmark is the deterministic regression net.
- Every number here comes from an actual run of the checked-in `bench.py` on the
  checked-in `seed/episodes.json`. No hardcoded or simulated results.
