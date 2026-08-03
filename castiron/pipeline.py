"""CastIron episode pipeline — P1 core flow.

    script
      ├─ narration : LadderTTSProvider (our cross-provider try/rung engine:
      │              elevenlabs → lmnt → hume; NOT genblaze fallback_models)
      ├─ music     : MockMusicProvider (Stability-shaped)
      └─ cover     : MockCoverProvider (GMI FLUX / DALL·E-shaped)
                 ↓  arun(max_concurrency=3)  — genblaze owns the fan-out
      ObjectStorageSink(LocalDirBackend, HIERARCHICAL) → runs/{date}/{run}/…
                 ↓  astream events → SQLite events table + SSE hub (live rail)
      read_manifest(verify=True) → SmartEmbedder → episode.mp3 (in-file manifest)

The three stages run in PARALLEL; the narration stage is itself a ladder that
tries distinct providers in order and records the ACTUAL rung in the manifest
(invariant I3). Always-green ``OFFLINE=1``: mock providers + LocalDirBackend,
zero network. LIVE mode (P2+) swaps the mock rungs for the real vendor providers.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from genblaze_core import KeyStrategy, Modality, ObjectStorageSink, Pipeline
from genblaze_core.providers.retry import RetryPolicy
from genblaze_core.storage.base import StorageBackend

from castiron.backends import make_media_backend
from castiron.chaos import ChaosSpec, narration_rung_down, resolve_chaos
from castiron.config import settings
from castiron.db import Database
from castiron.gate import GateResult, run_narration_gate
from castiron.hub import hub as default_hub
from castiron.ladder import LadderTTSProvider, Rung
from castiron.media import embed_manifest, synth_png, synth_tone, verify_file
from castiron.providers import LocalTTSProvider, MockCoverProvider, MockMusicProvider
from castiron.resume import ResumableTTSProvider

# Cross-provider TTS ladder (OFFLINE stand-in models mapping to the LIVE rungs
# ElevenLabs → LMNT → Hume). Order == rung order.
TTS_LADDER = ("elevenlabs-multilingual-v2", "lmnt-blizzard", "hume-octave")
TTS_RUNG_NAMES = ("elevenlabs", "lmnt", "hume")

STAGE_ORDER = ("narration", "music", "cover")
INDEX_TO_STAGE = dict(enumerate(STAGE_ORDER))
GATE_STAGE = "gate"

# Per-rung RetryPolicy (COMPLEXITY §3): premium TTS rungs get conservative()
# (few retries, documented duplicate-charge risk); the cheap last-resort rung
# (hume) gets aggressive() (cheap to hammer); tests get disabled() (one attempt =
# byte-identical to P1). MODEL_ERROR is non-retryable in every preset, so a
# provider *outage* still steps the ladder down on the first try.
def _retry_profiles() -> dict[str, list[RetryPolicy]]:
    return {
        "prod": [RetryPolicy.conservative(), RetryPolicy.conservative(),
                 RetryPolicy.aggressive()],
        "test": [RetryPolicy.disabled(), RetryPolicy.disabled(),
                 RetryPolicy.disabled()],
    }

DEFAULT_SCRIPT = (
    "Welcome to CastIron — the episode that survives an outage. "
    "When the primary voice provider goes dark, the ladder steps down a rung "
    "and the show still ships."
)


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #
@dataclass
class StageOutcome:
    name: str
    state: str
    provider_used: str | None
    model_used: str | None
    fallback_rung: int | None
    sha256: str | None
    b2_key: str | None


@dataclass
class EpisodeResult:
    run_id: str
    mode: str
    state: str
    # narration-ladder headline (kept for P0 compatibility)
    model_requested: str
    model_used: str
    fallback_used: bool
    cost_usd: float
    manifest_hash: str
    manifest_verified: bool
    episode_verified: bool
    embed_method: str
    episode_path: Path
    store_root: Path
    object_keys: list[str] = field(default_factory=list)
    stages: list[StageOutcome] = field(default_factory=list)
    event_types: list[str] = field(default_factory=list)
    # P2 resilience surface
    chaos: str | None = None
    resumed: bool = False
    budget_aborted: bool = False
    gate: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return (
            self.state == "completed"
            and self.manifest_verified
            and self.episode_verified
        )

    def stage(self, name: str) -> StageOutcome | None:
        return next((s for s in self.stages if s.name == name), None)


# --------------------------------------------------------------------------- #
# Fixtures + pipeline construction
# --------------------------------------------------------------------------- #
def _script_sha(script: str) -> str:
    return hashlib.sha256(script.encode()).hexdigest()[:16]


def _synth_fixtures(work: Path) -> tuple[Path, Path, Path]:
    work.mkdir(parents=True, exist_ok=True)
    narration = synth_tone(work / "narration.mp3", seconds=1.5, freq=330, mp3=True)
    music = synth_tone(work / "music.mp3", seconds=1.5, freq=220, mp3=True)
    cover = synth_png(work / "cover.png")
    return narration, music, cover


def _make_rung(
    i: int,
    narration_audio: Path,
    spec: ChaosSpec,
    retry: RetryPolicy,
    *,
    live: bool = False,
) -> Rung:
    """Build ladder rung ``i`` honoring the chaos spec + its retry policy.

    Transient narration chaos swaps rung 0 for a :class:`ResumableTTSProvider`
    (submit → transient death → the ladder resumes it, single charge — A9/I5).
    LIVE mode swaps the mock rung for the real vendor (ElevenLabs / LMNT / Hume),
    which writes real narration bytes into ``narration_audio``; OFFLINE keeps the
    deterministic local stand-in. Chaos injection (``should_fail``) is identical
    either way, so the cross-provider failover behaves the same LIVE.
    """
    if spec.is_transient and spec.hits_stage("narration") and i == 0:
        provider = ResumableTTSProvider(narration_audio, name=TTS_RUNG_NAMES[i])
    elif live:
        from castiron.live_providers import make_live_tts
        provider = make_live_tts(
            TTS_RUNG_NAMES[i], narration_audio, should_fail=narration_rung_down(spec, i)
        )
    else:
        provider = LocalTTSProvider(
            narration_audio,
            name=TTS_RUNG_NAMES[i],
            should_fail=narration_rung_down(spec, i),
        )
    return Rung(provider=provider, model=TTS_LADDER[i], name=TTS_RUNG_NAMES[i], retry=retry)


def build_episode_pipeline(
    base: Path,
    narration_audio: Path,
    music_audio: Path,
    cover_image: Path,
    *,
    script: str,
    music_style: str = "ambient",
    chaos: str | ChaosSpec | None = None,
    retry_profile: str = "prod",
    on_fallback: Any = None,
    on_retry: Any = None,
    on_resume: Any = None,
) -> tuple[Pipeline, ObjectStorageSink, StorageBackend]:
    """Assemble the 3-stage fan-out pipeline (narration ladder + music + cover)."""
    backend = make_media_backend(base)
    sink = ObjectStorageSink(backend, prefix="runs", key_strategy=KeyStrategy.HIERARCHICAL)
    spec = resolve_chaos(chaos)
    policies = _retry_profiles().get(retry_profile, _retry_profiles()["prod"])

    live = not settings.offline
    rungs = [_make_rung(i, narration_audio, spec, policies[i], live=live)
             for i in range(len(TTS_LADDER))]
    narration = LadderTTSProvider(rungs, on_fallback=on_fallback,
                                  on_retry=on_retry, on_resume=on_resume)
    if live:
        from castiron.live_providers import make_live_cover, make_live_music
        music = make_live_music(music_audio, should_fail=spec.hits_stage("music"))
        cover = make_live_cover(cover_image, should_fail=spec.hits_stage("cover"))
    else:
        music = MockMusicProvider(music_audio, should_fail=spec.hits_stage("music"))
        cover = MockCoverProvider(cover_image, should_fail=spec.hits_stage("cover"))

    pipe = (
        Pipeline("episode", preflight=False)
        .step(narration, model=TTS_LADDER[0], prompt=script, modality=Modality.AUDIO)
        .step(music, model="stable-audio-2", prompt=f"instrumental bed, {music_style}",
              modality=Modality.AUDIO)
        .step(cover, model="flux-1-schnell", prompt=f"podcast cover, {music_style}",
              modality=Modality.IMAGE)
    )
    return pipe, sink, backend


# --------------------------------------------------------------------------- #
# Event → SSE payload + persistence
# --------------------------------------------------------------------------- #
def event_payload(ev: Any, run_id: str) -> dict[str, Any]:
    """Compact, JSON-safe SSE payload for one stream event.

    Deliberately hand-built (not ``ev.model_dump()``) because terminal events
    carry a live ``PipelineResult``/``Step`` object; this keeps the wire payload
    small, serializable, and stable for the UI stage rail.
    """
    ts = getattr(ev, "timestamp", None)
    payload: dict[str, Any] = {
        "type": ev.type,
        "run_id": run_id,
        "at": ts.isoformat() if hasattr(ts, "isoformat") else ts,
    }
    for attr in ("step_index", "provider", "model", "progress_pct", "elapsed_sec",
                 "total_steps", "message", "error"):
        val = getattr(ev, attr, None)
        if val is not None:
            payload[attr] = val
    idx = getattr(ev, "step_index", None)
    if idx is not None and idx in INDEX_TO_STAGE:
        payload["stage"] = INDEX_TO_STAGE[idx]
    step = getattr(ev, "step", None)
    if step is not None:
        meta = getattr(step, "metadata", {}) or {}
        ladder = meta.get("ladder")
        if ladder:
            payload["rung"] = ladder.get("provider")
            payload["rung_index"] = ladder.get("rung_index")
            payload["fell_back"] = ladder.get("fell_back")
        payload["step_status"] = getattr(step, "status", None)
    if ev.type == "pipeline.completed":
        payload["manifest_hash"] = getattr(ev, "manifest_hash", None)
    return payload


def _handle_event(
    db: Database, run_id: str, ev: Any, hub: Any, publish: bool,
) -> None:
    payload = event_payload(ev, run_id)
    db.insert_event(run_id, "pipeline", ev.type, json.dumps(payload), payload.get("at"))
    if publish:
        hub.publish(run_id, payload)

    idx = getattr(ev, "step_index", None)
    stage_name = INDEX_TO_STAGE.get(idx) if idx is not None else None
    if stage_name is None:
        return

    if ev.type == "step.started":
        db.upsert_stage(run_id, stage_name, state="running",
                        provider_used=getattr(ev, "provider", None),
                        model_used=getattr(ev, "model", None),
                        started_at=payload.get("at"))
    elif ev.type in ("step.completed", "step.failed"):
        step = getattr(ev, "step", None)
        prov = getattr(ev, "provider", None)
        model = getattr(ev, "model", None)
        fallback_rung = None
        sha = None
        if step is not None:
            meta = getattr(step, "metadata", {}) or {}
            ladder = meta.get("ladder")
            if ladder:
                prov = ladder.get("provider")
                model = ladder.get("model")
                fallback_rung = ladder.get("rung_index")
            assets = getattr(step, "assets", None) or []
            if assets:
                sha = getattr(assets[0], "sha256", None)
        db.upsert_stage(
            run_id, stage_name,
            state="succeeded" if ev.type == "step.completed" else "failed",
            provider_used=prov, model_used=model, fallback_rung=fallback_rung,
            sha256=sha, finished_at=payload.get("at"),
        )


def _asset_keys_by_stage(run: Any) -> dict[str, str]:
    """Map stage name → stored object key using the run's per-step assets."""
    out: dict[str, str] = {}
    for step in run.steps:
        stage = INDEX_TO_STAGE.get(getattr(step, "step_index", None))
        assets = getattr(step, "assets", None) or []
        if stage and assets:
            url = getattr(assets[0], "url", "") or ""
            out[stage] = url.split("/b2/", 1)[-1] if "/b2/" in url else url
    return out


# Σ min_cost of the cheapest rung per stage (narration 0.002 + music 0.004 +
# cover 0.003). Used by the budget invariant projection (COMPLEXITY §3).
MIN_EPISODE_COST_USD = 0.009
BUDGET_DEMO_CAP_USD = 0.0005  # chaos=budget forces the projection over this cap


def _gate_event_sink(db: Database, run_id: str, hub: Any, publish: bool):
    """Return an ``on_event`` callback that persists gate events to DB + SSE."""
    def _emit(ev: dict[str, Any]) -> None:
        payload = {"run_id": run_id, "stage": GATE_STAGE, **ev}
        db.insert_event(run_id, "gate", ev["type"], json.dumps(payload))
        if publish:
            hub.publish(run_id, payload)
        if ev["type"] == "gate.completed":
            db.upsert_stage(
                run_id, GATE_STAGE,
                state="succeeded" if ev.get("passed") else "degraded",
                provider_used="agentloop", model_used="narration-gate",
                attempt=int(ev.get("iterations", 0)),
            )
    return _emit


# --------------------------------------------------------------------------- #
# The runner
# --------------------------------------------------------------------------- #
async def run_episode(
    *,
    script: str = DEFAULT_SCRIPT,
    voice: str = "narrator",
    music_style: str = "ambient",
    chaos: str | ChaosSpec | None = None,
    gate: bool = False,
    retry_profile: str = "prod",
    budget_cap: float | None = None,
    store_root: Path | None = None,
    run_id: str | None = None,
    db: Database | None = None,
    hub: Any = None,
    publish: bool = True,
) -> EpisodeResult:
    """Produce one episode: parallel 3-stage fan-out, persisted + streamed.

    Records every stream event to the ``events`` table and (optionally) the SSE
    hub; updates ``runs``/``stages``; then reads the manifest and embeds the
    episode. Always returns an ``EpisodeResult`` (``ok`` is False on failure).

    P2 knobs: ``gate`` runs the AgentLoop narration quality gate first; ``chaos``
    accepts the E12 ``CHAOS_FAIL`` control (provider[:stage][:timing]); a transient
    narration fault resumes rather than resubmits (single charge); ``chaos=budget``
    trips the ``MAX_RUN_COST_USD`` projection → typed ``BUDGET_ABORT``.
    """
    run_id = run_id or uuid.uuid4().hex[:12]
    db = db or Database(":memory:")
    hub = hub if hub is not None else default_hub
    base = Path(store_root or settings.local_store) / run_id
    # Synth scratch inputs live under the system temp dir: genblaze's S3 asset
    # transfer only reads local source files from its ALLOWED_FILE_ROOTS (temp),
    # so keeping them here (not under var/local-store) lets the LIVE sink upload
    # them. Harmless for OFFLINE — LocalDirBackend copies bytes regardless.
    work = Path(tempfile.gettempdir()) / "castiron-work" / run_id
    narration_audio, music_audio, cover_image = _synth_fixtures(work)
    spec = resolve_chaos(chaos)
    chaos_token = spec.to_token()

    if db.get_run(run_id) is None:
        db.insert_run(run_id, state="running", script_sha=_script_sha(script),
                      voice=voice, music_style=music_style, chaos_flag=chaos_token)
    else:
        db.update_run(run_id, state="running")
    for name in STAGE_ORDER:
        db.upsert_stage(run_id, name, state="pending")

    # --- Budget invariant (COMPLEXITY §3 / I-econ): hard-abort BEFORE spend ---
    cap = BUDGET_DEMO_CAP_USD if spec.is_budget else (
        budget_cap if budget_cap is not None else settings.max_run_cost_usd)
    projected = MIN_EPISODE_COST_USD
    if projected > cap:
        reason = (f"BUDGET_ABORT: projected ${projected:.4f} exceeds cap ${cap:.4f} "
                  f"(Σ min_cost before rung escalation)")
        payload = {"type": "budget.abort", "run_id": run_id, "reason": "BUDGET_ABORT",
                   "projected_usd": projected, "cap_usd": cap, "message": reason}
        db.insert_event(run_id, "gate", "budget.abort", json.dumps(payload))
        if publish:
            hub.publish(run_id, payload)
            hub.mark_done(run_id)
        db.update_run(run_id, state="failed", error=reason)
        for name in STAGE_ORDER:
            db.upsert_stage(run_id, name, state="aborted")
        return _degraded_result(run_id, base, chaos_token, state="failed",
                                budget_aborted=True, db=db)

    # --- AgentLoop narration quality gate (B4) --------------------------------
    gate_summary: dict[str, Any] | None = None
    if gate:
        db.upsert_stage(run_id, GATE_STAGE, state="running",
                        provider_used="agentloop", model_used="narration-gate")
        gate_result: GateResult = await run_narration_gate(
            script=script, asset_path=narration_audio,
            on_event=_gate_event_sink(db, run_id, hub, publish),
        )
        gate_summary = {
            "passed": gate_result.passed,
            "iterations": gate_result.iterations,
            "refinements": gate_result.refinements,
            "final_score": round(gate_result.final_score, 3),
            "cost_usd": round(gate_result.total_cost_usd, 4),
            "feedback_history": gate_result.feedback_history,
            "accepted_quality": gate_result.accepted_quality,
        }

    resumed_flag = {"v": False}

    def _side(ev_type: str, extra: dict[str, Any]) -> None:
        """Persist a ladder side-event to the DB (durable) + nudge the hub (live)."""
        full = {"type": ev_type, "run_id": run_id, "stage": "narration", **extra}
        db.insert_event(run_id, "pipeline", ev_type, json.dumps(full))
        if publish:
            hub.publish(run_id, full)

    def _on_fallback(i, r, e):  # noqa: ANN001
        _side("ladder.fallback", {"from_rung": i, "provider": r.name, "error": str(e)})

    def _on_retry(i, r, a, e):  # noqa: ANN001
        _side("ladder.retry", {"rung": i, "provider": r.name, "attempt": a,
                               "error": str(e)})

    def _on_resume(i, r, pid):  # noqa: ANN001
        resumed_flag["v"] = True
        _side("stage.resumed", {"rung": i, "provider": r.name, "prediction_id": pid,
                                "note": "resumed in-flight prediction — single charge (I5)"})

    pipe, sink, backend = build_episode_pipeline(
        base, narration_audio, music_audio, cover_image,
        script=script, music_style=music_style, chaos=spec, retry_profile=retry_profile,
        on_fallback=_on_fallback, on_retry=_on_retry, on_resume=_on_resume,
    )

    event_types: list[str] = []
    result = None
    state = "running"
    error: str | None = None
    try:
        async for ev in pipe.astream(sink=sink, max_concurrency=3, heartbeats=False,
                                     raise_on_failure=False):
            event_types.append(ev.type)
            _handle_event(db, run_id, ev, hub, publish)
            if ev.type == "pipeline.completed":
                result = ev.result
                state = "completed"
            elif ev.type == "pipeline.failed":
                result = getattr(ev, "result", None)
                state = "failed"
                error = getattr(ev, "message", None)
    except Exception as exc:  # noqa: BLE001  (record + degrade, never crash the run task)
        state = "failed"
        error = f"{type(exc).__name__}: {exc}"

    episode = base / "b2" / settings.published_bucket / "episode.mp3"
    manifest_hash = ""
    manifest_verified = False
    episode_verified = False
    embed_method = "-"
    cost = 0.0
    stages: list[StageOutcome] = []
    object_keys: list[str] = []

    if state == "completed" and result is not None:
        run = result.run
        manifest = sink.read_manifest(run, verify=True)
        manifest_hash = manifest.canonical_hash
        manifest_verified = manifest.verify()
        embed = embed_manifest(narration_audio, manifest, output=episode)
        embed_method = getattr(embed, "method", "?")
        episode_verified = verify_file(episode)
        cost = sum((s.cost_usd or 0.0) for s in run.steps)
        object_keys = [e.key for e in backend.list().entries]
        keys_by_stage = _asset_keys_by_stage(run)
        for st in db.list_stages(run_id):
            if st.name in keys_by_stage and not st.b2_key:
                db.upsert_stage(run_id, st.name, b2_key=keys_by_stage[st.name])
        db.update_run(run_id, state="completed", manifest_hash=manifest_hash,
                      episode_key=str(episode.relative_to(base)))
    else:
        db.update_run(run_id, state=state or "failed", error=error)

    for st in db.list_stages(run_id):
        stages.append(StageOutcome(
            name=st.name, state=st.state, provider_used=st.provider_used,
            model_used=st.model_used, fallback_rung=st.fallback_rung,
            sha256=st.sha256, b2_key=st.b2_key,
        ))

    if publish:
        hub.mark_done(run_id)

    narr = next((s for s in stages if s.name == "narration"), None)
    model_used = (narr.model_used if narr and narr.model_used else TTS_LADDER[0])
    fallback_used = bool(narr and narr.fallback_rung not in (None, 0))

    return EpisodeResult(
        run_id=run_id,
        mode=settings.mode,
        state=state,
        model_requested=TTS_LADDER[0],
        model_used=model_used,
        fallback_used=fallback_used,
        cost_usd=cost,
        manifest_hash=manifest_hash,
        manifest_verified=manifest_verified,
        episode_verified=episode_verified,
        embed_method=embed_method,
        episode_path=episode,
        store_root=base,
        object_keys=object_keys,
        stages=stages,
        event_types=event_types,
        chaos=chaos_token,
        resumed=resumed_flag["v"],
        budget_aborted=False,
        gate=gate_summary,
    )


def _degraded_result(
    run_id: str, base: Path, chaos_token: str, *, state: str,
    budget_aborted: bool, db: Database,
) -> EpisodeResult:
    """Build a typed-DEGRADED EpisodeResult (e.g. BUDGET_ABORT) — no assets."""
    stages = [
        StageOutcome(name=st.name, state=st.state, provider_used=st.provider_used,
                     model_used=st.model_used, fallback_rung=st.fallback_rung,
                     sha256=st.sha256, b2_key=st.b2_key)
        for st in db.list_stages(run_id)
    ]
    return EpisodeResult(
        run_id=run_id, mode=settings.mode, state=state,
        model_requested=TTS_LADDER[0], model_used=TTS_LADDER[0], fallback_used=False,
        cost_usd=0.0, manifest_hash="", manifest_verified=False, episode_verified=False,
        embed_method="-", episode_path=base / "b2" / settings.published_bucket / "episode.mp3",
        store_root=base, object_keys=[], stages=stages, event_types=[],
        chaos=chaos_token, resumed=False, budget_aborted=budget_aborted, gate=None,
    )


def run_offline_episode(
    *,
    script: str = DEFAULT_SCRIPT,
    chaos: str | ChaosSpec | None = None,
    gate: bool = False,
    retry_profile: str = "test",
    budget_cap: float | None = None,
    store_root: Path | None = None,
    run_id: str | None = None,
    db: Database | None = None,
) -> EpisodeResult:
    """Synchronous convenience wrapper (P0 tests + verify_offline).

    Runs the full 3-stage fan-out to completion with no SSE publishing and a
    throwaway in-memory DB (unless one is supplied). Defaults to the ``test``
    retry profile (``disabled()`` per rung) so the offline path is deterministic
    and byte-identical to P1 unless a chaos/gate knob is supplied.
    """
    run_id = run_id or uuid.uuid4().hex[:12]
    return asyncio.run(run_episode(
        script=script, chaos=chaos, gate=gate, retry_profile=retry_profile,
        budget_cap=budget_cap, store_root=store_root, run_id=run_id,
        db=db or Database(":memory:"), publish=False,
    ))


__all__ = [
    "DEFAULT_SCRIPT",
    "EpisodeResult",
    "INDEX_TO_STAGE",
    "STAGE_ORDER",
    "StageOutcome",
    "TTS_LADDER",
    "TTS_RUNG_NAMES",
    "build_episode_pipeline",
    "event_payload",
    "run_episode",
    "run_offline_episode",
]
