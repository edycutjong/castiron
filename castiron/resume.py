"""Transient resume, single-charge (A9 · invariant I5).

genblaze 0.4.0 added transient-error **job resumption**: when a worker dies
mid-generation, you resume the in-flight prediction instead of resubmitting, so
the provider bills the step **once**. CastIron demonstrates it end-to-end:

1. A rung *submits* (incurring the charge) and returns a ``prediction_id``, then
   the worker dies — a transient ``TIMEOUT``.
2. Instead of resubmitting (which would create a *second* prediction and a
   *second* charge), we call ``Pipeline.aresume_step(step, prediction_id, provider)``
   — which delegates to ``provider.aresume`` — skipping ``submit()`` and going
   straight to fetch-output.
3. Summing ``step.cost_usd`` shows **exactly one** charge (there is no
   ``CostLedger`` class in 0.4.1 — see DEVIATIONS F-03 — so the invariant is
   asserted by summing the step field the SDK actually exposes).

``ResumableTTSProvider`` is the OFFLINE stand-in; in LIVE the real vendor provider
already implements ``submit``/``resume`` and the same harness applies.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from genblaze_core import Modality, Pipeline
from genblaze_core.exceptions import ProviderError
from genblaze_core.models.asset import Asset
from genblaze_core.models.enums import ProviderErrorCode
from genblaze_core.models.step import Step
from genblaze_core.providers.base import SyncProvider

from castiron.ladder import PENDING_PREDICTION_KEY

DEFAULT_CHARGE_USD = 0.002


class ResumableTTSProvider(SyncProvider):
    """A provider that submits (charges once), dies transiently, then resumes.

    Tracks ``submit_count`` / ``resume_count`` so a test can prove the resume path
    never re-submitted (which is what would double-bill).
    """

    def __init__(
        self,
        asset_path: Path | None = None,
        *,
        name: str = "resumable-tts",
        cost_usd: float = DEFAULT_CHARGE_USD,
        transient_code: ProviderErrorCode = ProviderErrorCode.TIMEOUT,
    ) -> None:
        super().__init__()
        self.name = name  # type: ignore[assignment]
        self._asset_path = Path(asset_path) if asset_path else None
        self.cost_usd = cost_usd
        self._transient_code = transient_code
        self.submit_count = 0
        self.resume_count = 0

    def _asset(self) -> Asset:
        if self._asset_path and self._asset_path.exists():
            raw = self._asset_path.read_bytes()
            return Asset(url=self._asset_path.as_uri(), media_type="audio/mpeg",
                         sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw))
        return Asset(url="file:///dev/null/narration.mp3", media_type="audio/mpeg",
                     sha256=hashlib.sha256(b"resumed").hexdigest(), size_bytes=7)

    def generate(self, step, config=None):  # noqa: ANN001
        # SUBMIT: the charge is incurred and a prediction id is issued...
        self.submit_count += 1
        prediction_id = f"pred-{self.name}-{self.submit_count}"
        step.cost_usd = self.cost_usd
        step.metadata[PENDING_PREDICTION_KEY] = prediction_id
        step.provider_payload = {"prediction_id": prediction_id, "submitted": True}
        # ...then the worker dies mid-generation → transient error (job survives).
        raise ProviderError(
            "worker died mid-generation (transient); prediction is in flight",
            error_code=self._transient_code,
        )

    def _finish(self, prediction_id, step) -> Step:  # noqa: ANN001
        self.resume_count += 1
        resumed = step.model_copy()
        resumed.assets = [self._asset()]
        # cost_usd was set at submit and copies over — DO NOT re-charge (I5).
        resumed.metadata = dict(resumed.metadata or {})
        resumed.metadata.pop(PENDING_PREDICTION_KEY, None)
        resumed.metadata["resumed_from"] = str(prediction_id)
        resumed.status = "completed"
        return resumed

    def resume(self, prediction_id, step, config=None):  # noqa: ANN001
        return self._finish(prediction_id, step)

    async def aresume(self, prediction_id, step, config=None):  # noqa: ANN001
        return self._finish(prediction_id, step)


@dataclass
class ResumeOutcome:
    """Proof record for the single-charge invariant."""

    submit_count: int
    resume_count: int
    total_charge_usd: float
    charged_once: bool
    asset_present: bool
    prediction_id: str | None
    used: str  # "resume_step" | "aresume_step"

    def as_dict(self) -> dict[str, Any]:
        return {
            "submit_count": self.submit_count,
            "resume_count": self.resume_count,
            "total_charge_usd": round(self.total_charge_usd, 6),
            "charged_once": self.charged_once,
            "asset_present": self.asset_present,
            "prediction_id": self.prediction_id,
            "resume_primitive": self.used,
        }


def _new_step() -> Step:
    return Step(provider="resumable-tts", model="narration", modality=Modality.AUDIO,
                prompt="resume-demo")


async def resume_after_transient(
    *,
    asset_path: Path | None = None,
    cost_usd: float = DEFAULT_CHARGE_USD,
    use_async: bool = True,
) -> ResumeOutcome:
    """Inject a transient mid-generation failure and resume it (single charge).

    Uses ``Pipeline.aresume_step`` (async, the app's path) or ``resume_step``
    (sync). Returns a :class:`ResumeOutcome` whose ``charged_once`` is the
    invariant-I5 verdict.
    """
    provider = ResumableTTSProvider(asset_path, cost_usd=cost_usd)
    step = _new_step()
    prediction_id: str | None = None
    try:
        provider.generate(step)  # submit → charge → transient death
    except ProviderError:
        prediction_id = step.metadata.get(PENDING_PREDICTION_KEY)

    pipe = Pipeline("resume-demo", preflight=False)
    if use_async:
        resumed = await pipe.aresume_step(step, prediction_id, provider)
        used = "aresume_step"
    else:
        resumed = pipe.resume_step(step, prediction_id, provider)
        used = "resume_step"

    total = resumed.cost_usd or 0.0
    return ResumeOutcome(
        submit_count=provider.submit_count,
        resume_count=provider.resume_count,
        total_charge_usd=total,
        charged_once=(provider.submit_count == 1 and abs(total - cost_usd) < 1e-9),
        asset_present=bool(resumed.assets),
        prediction_id=prediction_id,
        used=used,
    )


def resume_after_transient_sync(**kwargs: Any) -> ResumeOutcome:
    return asyncio.run(resume_after_transient(**kwargs))


def resubmit_double_charge(cost_usd: float = DEFAULT_CHARGE_USD) -> float:
    """The counterfactual: naive RESUBMIT bills twice (what resume avoids)."""
    provider = ResumableTTSProvider(cost_usd=cost_usd)
    charged = 0.0
    for _ in range(2):
        step = _new_step()
        try:
            provider.generate(step)
        except ProviderError:
            charged += step.cost_usd or 0.0
    return charged


__all__ = [
    "ResumableTTSProvider",
    "ResumeOutcome",
    "resubmit_double_charge",
    "resume_after_transient",
    "resume_after_transient_sync",
]
