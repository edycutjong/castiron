# Genblaze friction log

Dated, reproducible frictions hit while building CastIron against the real SDK.
Feeds `../FEEDBACK_DOSSIER.md` (≥5 issues by Freeze). Each entry: what we hit,
where it bit, our workaround, and whether it's a genuine upstream feedback issue
(vs. a spec-vs-SDK naming mismatch that's ours to correct).

Repro base: `genblaze==0.4.1` (genblaze-core 0.3.4, genblaze-s3 0.3.4), Python
3.11, installed via `uv sync`. Surface dumped by `scripts/sdk_introspect.py`.

---

## 2026-07-04 · P0 spike

### F-01 · No `genblaze` CLI ships — `genblaze verify` / `extract` are Python-only  ⇒ DOSSIER
- **Hit:** the dev-guide and our spec (SDK_COVERAGE ✅ "CLI verify/extract/index/replay")
  show `genblaze verify episode.mp3`. Reality: 0.4.1 installs **no** `genblaze`
  console-script, no `genblaze.__main__`, no `cli` module.
  Repro: `python -m genblaze --help` → "No module named genblaze.__main__";
  `importlib.metadata.entry_points(group="console_scripts")` has no `genblaze`.
- **Impact:** the P0 exit-test line "MP3 … that `genblaze verify` accepts" can't run
  as written. Verify is available as a **Python API**: `get_handler(mime).verify(path)`
  (== extract + `Manifest.verify()`), which we use in `castiron.media.verify_file`.
- **Workaround:** CastIron ships its own `castiron verify` thin CLI (P6) over these
  handler methods. **Upstream ask:** ship the documented `genblaze` CLI, or drop
  verify/extract from the guide until it lands.

### F-02 · No `FailingProvider` / `ModelErrorProvider` classes  ⇒ DOSSIER (docs)
- **Hit:** ARCHITECTURE + SDK_COVERAGE list "Mock/Failing/ModelError providers".
  `genblaze_core.testing` exports only `MockProvider`, `MockAudioProvider`,
  `MockVideoProvider`. Failure is a **parameter**: `MockProvider(should_fail=True,
  error_code=ProviderErrorCode.SERVER_ERROR)`.
- **Impact:** chaos matrix + P0 "FailingProvider fallback observed" needed a shim.
- **Workaround:** `castiron.providers.failing_provider()` wraps `MockProvider(
  should_fail=True)`. **Upstream ask:** either add the named classes or fix docs
  that imply them.

### F-03 · No `CostLedger` class — cost lives on `step.cost_usd`  ⇒ spec-correction (not upstream)
- **Hit:** COMPLEXITY §3 / invariant I5 reference a `CostLedger`. Grep of
  genblaze-core: **0 hits**. Real surface: `step.cost_usd` (float per step),
  `AgentResult.total_cost_usd`, and a `total_cost_usd` event field.
- **Impact:** our cost meter + single-charge invariant assert must sum
  `step.cost_usd`, not read a ledger object.
- **Workaround:** documented in DEVIATIONS; capability fully present, only the
  spec's name was wrong — not a dossier issue.

### F-04 · MP3 manifest embedding silently degrades to a sidecar without `mutagen`  ⇒ DOSSIER
- **Hit:** `SmartEmbedder().embed(x.mp3, manifest)` with no `mutagen` installed
  returns `EmbedResult(method="sidecar", embed_error="mutagen package required…")`
  and writes `x.mp3.genblaze.json` — but only **logs** a warning; the call
  "succeeds". Then `Mp3Handler.verify()` raises `ModuleNotFoundError`.
- **Impact:** an unwary build ships episodes with **no in-file provenance** and
  discovers it only at verify time.
- **Workaround:** depend on `mutagen` directly (not the heavy `[audio]` extra) so
  `method="inline"`. **Upstream ask:** make silent sidecar-fallback opt-in, or
  surface it as a first-class warning/return the caller must acknowledge.

### F-05 · `Manifest.verify()` does not re-hash the asset payload  ⇒ DOSSIER
- **Hit:** `verify()` = `verify_hash()` (canonical_hash over the run record) + every
  output declaring a 64-hex `sha256`. Docstring is explicit: "It does not fetch
  `asset.url` or re-hash remote bytes." So editing the **embedded manifest** trips
  verify (good), but **re-encoding the audio** does not.
  Repro: flip a byte in `episode.mp3` audio frames → `verify()` still `True`.
- **Impact:** our tamper red-path catches provenance edits today; catching an audio
  re-encode needs a payload re-hash CastIron adds at publish (P4).
- **Workaround:** P4 `verify_episode()` recomputes the audio-stream sha256 vs the
  manifest's recorded `asset.sha256`. **Upstream ask:** `verify(re_hash=True)`.

### F-06 · `ObjectStorageSink` writes a run-level `manifest.json`; in-file embed is separate
- **Hit:** running a pipeline with `sink=ObjectStorageSink(...)` stores the raw
  asset + a sibling `runs/…/manifest.json`; it does **not** embed the manifest into
  the audio file. In-file embedding is a distinct `SmartEmbedder`/handler step.
- **Impact:** the published episode must be produced by an explicit embed pass; the
  spec's "in-file manifests" only exist after we run the embedder.
- **Workaround:** `castiron.pipeline` embeds the manifest read back from the sink
  into `episode.mp3` before "publishing". Not a bug — a spec assumption corrected.

### F-07 · `Pipeline.run()` requires explicit `raise_on_failure=` (0.4.0)  ⇒ minor
- **Hit:** `run()` warns "will raise PipelineError on step failure starting in
  genblaze-core 0.4.0. Pass raise_on_failure=True/False."
- **Workaround:** we pass it explicitly everywhere (True for happy path, False when
  we want to observe a failed run). Noise only; noted so future sessions don't chase it.

---

## 2026-07-04 · P1 core flow

### F-08 · `fallback_models` is in-provider only — no cross-provider ladder  ⇒ DOSSIER (issue-01)
- **Hit:** building the narration failover (ElevenLabs→LMNT→Hume). `.step()` takes one
  `provider=` and `fallback_models: list[str]` (alternate MODELS on that same provider).
  There is no `fallback_providers=` — an account-level outage of the primary provider
  takes every `fallback_models` rung with it. `inspect.signature(Pipeline.step)` confirms.
- **Impact:** the cross-provider ladder is CastIron's headline resilience feature; we had
  to write our own composite `LadderTTSProvider(SyncProvider)` that loops over distinct
  sub-providers and records the winning rung in `step.metadata`/`step.model`.
- **Verified:** mutating `step.model` + `step.metadata` inside a custom provider's
  `generate()` DOES persist into the run manifest (spike), so the actual rung is recorded
  (I3). **Upstream ask:** a `Ladder`/`Rung` primitive or `.step(fallback_providers=[...])`.
  Drafted as `docs/dossier-issues/issue-01-cross-provider-fallback.md`.

### F-09 · streaming/fan-out surface (positive) — `astream(max_concurrency=)` + typed events
- **Confirmed working:** `Pipeline.astream(sink=, max_concurrency=3, heartbeats=False,
  raise_on_failure=False)` drives a parallel 3-step run and yields typed pydantic events
  from `genblaze_core.observability.events` (`pipeline.started`, `step.queued/started/
  progress/completed/failed/retried`, `pipeline.completed/failed`). `step.started` carries
  the requested model; `step.completed` carries the actual model — a fallback is visible
  mid-stream. `.model_dump()` is JSON-safe except the terminal `result`/`step` objects
  (we build a compact SSE payload by hand). No friction — recorded so P2 builds on it.
