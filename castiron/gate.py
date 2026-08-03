"""AgentLoop narration quality gate (B4) — generate → evaluate → refine.

COMPLEXITY §1 places a gate between narration and publish:

    GATE{ AgentLoop ≤3 · CallableEvaluator LUFS/silence/drift
                        + ThresholdEvaluator duration } --feedback--> narration

This module realizes it on the genblaze ``AgentLoop`` with **both** documented
evaluator types combined:

- :class:`~genblaze_core.CallableEvaluator` — the LUFS / silence / pacing scorer.
- :class:`~genblaze_core.ThresholdEvaluator` — a hard duration-drift bound (B4).

The two are combined by :class:`CompositeGate` (a real ``Evaluator`` subclass): a
result passes only if *both* pass, and the failing sub-feedbacks are concatenated
into one string that the loop threads into the next iteration via
``AgentContext.last_evaluation.feedback``. The ``pipeline_factory`` reads that
feedback and applies the pacing fix — so the loop genuinely refines, it does not
just retry.

The seeded flaw (SEED_DATA "space_update.md", em-dash cluster) is data-driven:
:func:`pacing_report` derives silence / loudness / duration purely from the script
text, so the gate **reproducibly fails iteration 0 and passes iteration 1** with no
randomness and no network. In LIVE mode the same scorer reads ffmpeg
``loudnorm``/``silencedetect`` numbers instead of the synthetic model (SDKCHK #12).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from genblaze_core import (
    AgentContext,
    AgentLoop,
    CallableEvaluator,
    EvaluationResult,
    Evaluator,
    Modality,
    Pipeline,
    ThresholdEvaluator,
)
from genblaze_core.providers.base import SyncProvider

from castiron.media import local_asset

# ---- quality bands (broadcast-ish; wide enough for the OFFLINE synthetic model) --
TARGET_LUFS = -16.0
LUFS_TOLERANCE = 2.0          # pass band = [-18.0, -14.0]
MAX_SILENCE_RATIO = 0.10
DURATION_TOLERANCE_SEC = 1.5  # ThresholdEvaluator bound
WORDS_PER_SEC = 2.5           # nominal narration rate
EMDASH_PAUSE_SEC = 1.15       # naive TTS over-pauses on each em-dash cluster
GATE_STEP_COST_USD = 0.002


@dataclass
class PacingReport:
    """Synthetic (OFFLINE) narration quality derived deterministically from text."""

    target_sec: float
    duration_sec: float
    silence_ratio: float
    lufs: float
    emdash_clusters: int
    fixed: bool

    @property
    def duration_drift(self) -> float:
        return abs(self.duration_sec - self.target_sec)

    @property
    def silence_ts(self) -> str:
        """A stable pseudo-timestamp for the worst silence (demo flavor)."""
        secs = int(min(self.target_sec, 41))
        return f"00:{secs:02d}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "lufs": round(self.lufs, 1),
            "silence_ratio": round(self.silence_ratio, 3),
            "duration_sec": round(self.duration_sec, 2),
            "target_sec": round(self.target_sec, 2),
            "duration_drift": round(self.duration_drift, 2),
            "emdash_clusters": self.emdash_clusters,
            "fixed": self.fixed,
        }


def pacing_report(script: str, *, fixed: bool) -> PacingReport:
    """Derive narration quality from the script (the em-dash pacing trap).

    Unfixed, each em-dash cluster injects a long pause → silence + duration drift
    and a lower integrated loudness. ``fixed=True`` (pacing normalization applied)
    collapses those pauses back into band.
    """
    words = max(len(script.split()), 1)
    target = words / WORDS_PER_SEC
    clusters = _emdash_clusters(script)
    pause = 0.0 if fixed else clusters * EMDASH_PAUSE_SEC
    duration = target + pause
    silence_ratio = (pause / duration) if duration else 0.0
    # residual, in-band silence even when fixed (natural sentence gaps)
    if fixed:
        silence_ratio = min(silence_ratio + 0.03, 0.06)
    # long dead air pulls integrated loudness down (quieter); fixed sits at target
    lufs = TARGET_LUFS - silence_ratio * 30.0
    return PacingReport(
        target_sec=target,
        duration_sec=duration if not fixed else target * 1.02,
        silence_ratio=silence_ratio,
        lufs=lufs,
        emdash_clusters=clusters,
        fixed=fixed,
    )


def _emdash_clusters(script: str) -> int:
    """Count em-dash pacing traps (—, ' -- ', or ' - ') in the script."""
    n = script.count("—")           # em-dash
    n += script.count(" -- ")
    if n == 0:
        n = script.count(" - ")          # hyphen-as-dash fallback
    return n


# --------------------------------------------------------------------------- #
# The OFFLINE gated narration provider
# --------------------------------------------------------------------------- #
class GatedNarrationProvider(SyncProvider):
    """Emits the narration asset + a synthetic quality report on the step.

    ``fixed`` toggles whether the pacing-normalization fix has been applied — the
    factory sets it from the threaded feedback. Real bytes + real sha256 flow
    through so the manifest/verify chain is exercised; only the *quality numbers*
    are synthetic in OFFLINE.
    """

    _stage = "narration"

    def __init__(self, asset_path: Path, script: str, *, fixed: bool,
                 name: str = "gated-tts", cost_usd: float = GATE_STEP_COST_USD) -> None:
        super().__init__()
        self.name = name  # type: ignore[assignment]
        self._asset_path = Path(asset_path)
        self._script = script
        self._fixed = fixed
        self._cost = cost_usd

    def generate(self, step, config=None):  # noqa: ANN001
        report = pacing_report(self._script, fixed=self._fixed)
        step.assets.append(local_asset(self._asset_path, media_type="audio/mpeg"))
        step.cost_usd = self._cost
        step.metadata["quality"] = report.as_dict()
        step.metadata.setdefault("stage", self._stage)
        step.metadata["pacing_fix_applied"] = self._fixed
        return step


def _quality(result) -> dict[str, Any]:
    return result.run.steps[0].metadata.get("quality", {})


# --------------------------------------------------------------------------- #
# Evaluators — BOTH documented types, combined
# --------------------------------------------------------------------------- #
def loudness_silence_evaluator() -> CallableEvaluator:
    """CallableEvaluator: LUFS band + silence ratio (the pacing scorer)."""

    def _fn(result) -> EvaluationResult:
        q = _quality(result)
        lufs = q.get("lufs", TARGET_LUFS)
        silence = q.get("silence_ratio", 0.0)
        ts = f"00:{int(min(q.get('target_sec', 41), 41)):02d}"
        problems: list[str] = []
        if silence > MAX_SILENCE_RATIO:
            problems.append(f"long silence at {ts} (dead-air {silence:.0%})")
        if lufs < TARGET_LUFS - LUFS_TOLERANCE:
            problems.append(f"integrated loudness {lufs:.1f} LUFS below target {TARGET_LUFS:.0f}")
        elif lufs > TARGET_LUFS + LUFS_TOLERANCE:
            problems.append(f"integrated loudness {lufs:.1f} LUFS too hot")
        passed = not problems
        # higher score = quieter dead-air; keeps it a real [0,1] quality signal
        score = max(0.0, 1.0 - silence)
        feedback = None if passed else "; ".join(problems) + " — normalize pacing"
        return EvaluationResult(passed=passed, score=score, feedback=feedback,
                                metadata={"lufs": lufs, "silence_ratio": silence})

    return CallableEvaluator(_fn)


def duration_evaluator(tol: float = DURATION_TOLERANCE_SEC) -> ThresholdEvaluator:
    """ThresholdEvaluator: hard bound on duration drift vs target (B4)."""

    def _score(result) -> float:
        return float(_quality(result).get("duration_drift", 0.0))

    def _feedback(result, score: float) -> str:
        q = _quality(result)
        return (f"narration {q.get('duration_sec', 0):.1f}s drifts {score:.1f}s beyond "
                f"{q.get('target_sec', 0):.1f}s target — tighten pacing")

    return ThresholdEvaluator(_score, tol, higher_is_better=False, feedback_fn=_feedback)


class CompositeGate(Evaluator):
    """Combine sub-evaluators: pass iff ALL pass; thread joined feedback.

    A real ``Evaluator`` subclass (not a lambda) so it is reusable and carries the
    combined score + metadata that the SSE rail and manifest note render.
    """

    def __init__(self, *evaluators: Evaluator) -> None:
        if not evaluators:
            raise ValueError("CompositeGate needs at least one evaluator")
        self._evaluators = evaluators

    def evaluate(self, result) -> EvaluationResult:  # noqa: ANN001
        subs = [e.evaluate(result) for e in self._evaluators]
        return self._combine(subs)

    async def aevaluate(self, result) -> EvaluationResult:  # noqa: ANN001
        subs = [await e.aevaluate(result) for e in self._evaluators]
        return self._combine(subs)

    @staticmethod
    def _combine(subs: list[EvaluationResult]) -> EvaluationResult:
        passed = all(s.passed for s in subs)
        fails = [s.feedback for s in subs if s.feedback and not s.passed]
        feedback = " | ".join(fails) if fails else None
        score = min((s.score if s.score is not None else 1.0) for s in subs)
        meta: dict[str, Any] = {}
        for s in subs:
            meta.update(s.metadata or {})
        return EvaluationResult(passed=passed, score=score, feedback=feedback, metadata=meta)


def build_gate_evaluator() -> CompositeGate:
    """The CastIron narration gate = LUFS/silence (Callable) + duration (Threshold)."""
    return CompositeGate(loudness_silence_evaluator(), duration_evaluator())


# --------------------------------------------------------------------------- #
# Result + runner
# --------------------------------------------------------------------------- #
@dataclass
class GateIteration:
    index: int
    passed: bool
    score: float
    feedback: str | None
    quality: dict[str, Any]
    fix_applied: bool


@dataclass
class GateResult:
    passed: bool
    iterations: int
    refinements: int                       # iterations beyond the first
    final_score: float
    total_cost_usd: float
    target_sec: float
    accepted_quality: dict[str, Any]
    records: list[GateIteration] = field(default_factory=list)
    feedback_history: list[str] = field(default_factory=list)

    @property
    def iterated(self) -> bool:
        return self.refinements >= 1


def _feedback_calls_for_fix(feedback: str | None) -> bool:
    """Does the threaded feedback ask for a pacing fix? (honest feedback wiring)."""
    if not feedback:
        return False
    low = feedback.lower()
    return any(k in low for k in ("silence", "pacing", "drift", "loudness", "lufs"))


async def run_narration_gate(
    *,
    script: str,
    asset_path: Path,
    max_iterations: int = 3,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> GateResult:
    """Drive the AgentLoop narration gate to acceptance (or ``max_iterations``).

    Returns a :class:`GateResult`. ``on_event`` (optional) receives ordered
    ``gate.iteration.started`` / ``gate.iteration.evaluated`` / ``gate.completed``
    payloads for the DB/SSE rail.
    """
    fix_log: list[bool] = []

    def factory(ctx: AgentContext) -> Pipeline:
        # Thread the feedback: apply the pacing fix iff the loop told us to.
        apply_fix = _feedback_calls_for_fix(
            ctx.last_evaluation.feedback if ctx.last_evaluation else None
        )
        fix_log.append(apply_fix)
        provider = GatedNarrationProvider(asset_path, script, fixed=apply_fix)
        return Pipeline("narration-gate", preflight=False).step(
            provider, model="narration-gate", prompt=script, modality=Modality.AUDIO
        )

    evaluator = build_gate_evaluator()
    loop = AgentLoop(factory, evaluator, max_iterations=max_iterations,
                     stop_on_pipeline_failure=True)
    agent_result = await loop.arun()

    records: list[GateIteration] = []
    feedback_history: list[str] = []
    for it in agent_result.iterations:
        q = it.result.run.steps[0].metadata.get("quality", {})
        fix_applied = bool(q.get("fixed", False))
        rec = GateIteration(
            index=it.index, passed=it.evaluation.passed,
            score=float(it.evaluation.score or 0.0),
            feedback=it.evaluation.feedback, quality=q, fix_applied=fix_applied,
        )
        records.append(rec)
        if on_event is not None:
            # emit "started" (with the feedback that seeded this iteration) then "evaluated"
            seed_fb = records[it.index - 1].feedback if it.index > 0 else None
            on_event({"type": "gate.iteration.started", "iteration": it.index,
                      "total": max_iterations, "feedback_in": seed_fb,
                      "fix_applied": fix_applied})
            on_event({"type": "gate.iteration.evaluated", "iteration": it.index,
                      "passed": rec.passed, "score": round(rec.score, 3),
                      "feedback": rec.feedback, "quality": q})
        if rec.feedback:
            feedback_history.append(rec.feedback)

    final_q = records[-1].quality if records else {}
    result = GateResult(
        passed=agent_result.passed,
        iterations=len(records),
        refinements=max(len(records) - 1, 0),
        final_score=float(agent_result.iterations[-1].evaluation.score or 0.0),
        total_cost_usd=agent_result.total_cost_usd,
        target_sec=float(final_q.get("target_sec", 0.0)),
        accepted_quality=final_q,
        records=records,
        feedback_history=feedback_history,
    )
    if on_event is not None:
        on_event({"type": "gate.completed", "passed": result.passed,
                  "iterations": result.iterations, "refinements": result.refinements,
                  "final_score": round(result.final_score, 3),
                  "cost_usd": round(result.total_cost_usd, 4)})
    return result


def run_narration_gate_sync(**kwargs: Any) -> GateResult:
    """Synchronous convenience wrapper (tests + verify_offline)."""
    return asyncio.run(run_narration_gate(**kwargs))


__all__ = [
    "CompositeGate",
    "GateIteration",
    "GateResult",
    "GatedNarrationProvider",
    "PacingReport",
    "build_gate_evaluator",
    "duration_evaluator",
    "loudness_silence_evaluator",
    "pacing_report",
    "run_narration_gate",
    "run_narration_gate_sync",
]
