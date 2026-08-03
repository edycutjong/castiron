"""CastIron cross-provider TTS ladder — our OWN try/rung failover engine.

Why this is not ``fallback_models``
-----------------------------------
genblaze's ``.step(..., fallback_models=[...])`` is **in-provider** failover: one
provider, several *models*. It cannot fail over to a *different provider* with a
different SDK, auth, and infra — which is the entire point of a resilience ladder
(provider independence = uncorrelated outage risk; ARCHITECTURE "Model selection").

So CastIron owns the cross-provider loop. ``LadderTTSProvider`` is a composite
``SyncProvider`` that wraps N **distinct** rungs (ElevenLabs → LMNT → Hume) and
tries each in order until one succeeds. Because it is itself a provider, it slots
into the pipeline as a single narration step and fans out in PARALLEL with music
and cover via genblaze ``arun(max_concurrency=3)`` — genblaze owns the fan-out,
CastIron owns the rung logic. This is the seed of the P6 ``genblaze-ladder`` pip
package (COMPLEXITY §4); extraction is mechanical.

P2 additions (resilience depth)
-------------------------------
- **Per-rung ``RetryPolicy``** (``Rung.retry``): before stepping *down* a rung we
  consult ``RetryPolicy.should_retry()`` for *transient* error codes. Expensive
  TTS rungs get ``conservative()`` (few retries, duplicate-charge risk); cheap
  rungs get ``aggressive()``; tests pass ``disabled()`` (one attempt = exact P1
  behavior). ``MODEL_ERROR`` is non-retryable in every preset, so a provider
  *outage* (the chaos path) still steps down on the first try — P1-identical.
- **Transient resume (A9 / invariant I5)**: if a rung raises a *transient* error
  but has already **submitted** (it left a ``pending_prediction_id`` on the step,
  i.e. the charge is incurred), the ladder **resumes** that prediction rather than
  resubmitting — exactly one provider charge for the step. Resume is the same call
  ``Pipeline.resume_step`` delegates to (``provider.resume``).

The winning rung is recorded on ``step.model`` (the actual model) and in
``step.metadata["ladder"]`` (index, provider, per-rung attempts incl. retries and
resumes). Both persist into the run manifest (verified empirically at build), so a
fallback is never hidden — invariant I3.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from genblaze_core.exceptions import ProviderError
from genblaze_core.models.enums import ProviderErrorCode
from genblaze_core.providers.base import SyncProvider
from genblaze_core.providers.retry import RetryPolicy

from castiron.config import settings

# key under which the ladder writes its provenance note in step.metadata
LADDER_META_KEY = "ladder"
# key a rung provider sets to signal "I submitted (and charged); resume me"
PENDING_PREDICTION_KEY = "pending_prediction_id"

# transient error codes: retry-eligible AND resume-eligible (match RetryPolicy
# preset retryable_codes verified at build: {timeout, server_error, rate_limit})
TRANSIENT_CODES = frozenset(
    {
        ProviderErrorCode.TIMEOUT,
        ProviderErrorCode.SERVER_ERROR,
        ProviderErrorCode.RATE_LIMIT,
    }
)


@dataclass
class Rung:
    """One rung of the ladder: a distinct provider + the model to ask it for.

    ``name`` is the human/UI label (``"elevenlabs"``); ``model`` is what the
    provider is called with (``"eleven_multilingual_v2"``). ``retry`` is the
    per-rung :class:`RetryPolicy`; ``None`` means *try once* (``disabled()``) so a
    rung with no explicit policy behaves exactly as the P1 ladder did.
    """

    provider: SyncProvider
    model: str
    name: str
    retry: RetryPolicy | None = None
    # populated at runtime with the effective policy actually applied
    _applied_policy: str = field(default="", repr=False)


def _err_code(exc: ProviderError) -> ProviderErrorCode | None:
    code = getattr(exc, "error_code", None)
    if isinstance(code, ProviderErrorCode):
        return code
    return None


def _code_value(code: ProviderErrorCode | None) -> str | None:
    return code.value if code is not None else None


def _policy_name(policy: RetryPolicy) -> str:
    """Best-effort human label for a RetryPolicy preset (for the manifest note)."""
    for label in ("disabled", "conservative", "aggressive"):
        preset = getattr(RetryPolicy, label)()
        if (preset.max_attempts, preset.retryable_codes) == (
            policy.max_attempts,
            policy.retryable_codes,
        ):
            return label
    return f"custom(max_attempts={policy.max_attempts})"


class LadderTTSProvider(SyncProvider):
    """Composite provider: try each rung's distinct provider until one succeeds.

    On success the winning rung's model becomes ``step.model`` and a ladder note
    is written to ``step.metadata``. If every rung fails, raises ``ProviderError``
    (``SERVER_ERROR``) carrying the collected attempts — the run then ends
    ``failed``/``DEGRADED`` rather than silently dropping.
    """

    def __init__(
        self,
        rungs: list[Rung],
        *,
        name: str = "castiron-tts-ladder",
        on_fallback: Callable[[int, Rung, ProviderError], None] | None = None,
        on_retry: Callable[[int, Rung, int, ProviderError], None] | None = None,
        on_resume: Callable[[int, Rung, str], None] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        super().__init__()
        if not rungs:
            raise ValueError("ladder needs at least one rung")
        self.name = name  # type: ignore[assignment]
        self.rungs = list(rungs)
        self._on_fallback = on_fallback
        self._on_retry = on_retry
        self._on_resume = on_resume
        # real backoff sleeps only when LIVE; OFFLINE/tests are deterministic and
        # instant (no wall-clock backoff needed for a mock outage).
        self._sleep = sleep_fn or (time.sleep if not settings.offline else (lambda _s: None))

    # -- one rung, with retry + transient-resume ------------------------------
    def _attempt_rung(
        self, idx: int, rung: Rung, step, config,
    ) -> tuple[bool, list[dict[str, Any]]]:
        """Try a single rung to success/exhaustion. Returns (succeeded, attempts)."""
        policy = rung.retry or RetryPolicy.disabled()
        rung._applied_policy = _policy_name(policy)
        attempts: list[dict[str, Any]] = []
        attempt = 1
        while True:
            step.model = rung.model
            step.assets = []
            step.cost_usd = None
            step.error = None
            step.error_code = None
            step.metadata.pop(PENDING_PREDICTION_KEY, None)
            try:
                rung.provider.generate(step, config)
            except ProviderError as exc:
                code = _err_code(exc)
                pending = step.metadata.get(PENDING_PREDICTION_KEY)
                # A9: submitted-then-transient → RESUME (single charge), do NOT resubmit
                if pending is not None and code in TRANSIENT_CODES:
                    resumed = rung.provider.resume(pending, step, config)  # same call resume_step delegates to
                    self._adopt_resumed(step, resumed, pending)
                    if self._on_resume is not None:
                        self._on_resume(idx, rung, str(pending))
                    attempts.append(_attempt_row(idx, rung, ok=True, code=code,
                                                 attempt=attempt, resumed=str(pending),
                                                 policy=rung._applied_policy))
                    return True, attempts
                # transient (no pending) → maybe retry the SAME rung
                if code in TRANSIENT_CODES and policy.should_retry(code, attempt) \
                        and attempt < policy.max_attempts:
                    attempts.append(_attempt_row(idx, rung, ok=False, code=code,
                                                 attempt=attempt, error=str(exc),
                                                 retried=True, policy=rung._applied_policy))
                    if self._on_retry is not None:
                        self._on_retry(idx, rung, attempt, exc)
                    self._sleep(policy.compute_delay(attempt))
                    attempt += 1
                    continue
                # give up on this rung → caller steps down
                attempts.append(_attempt_row(idx, rung, ok=False, code=code,
                                             attempt=attempt, error=str(exc),
                                             policy=rung._applied_policy))
                if self._on_fallback is not None:
                    self._on_fallback(idx, rung, exc)
                return False, attempts

            # success on this rung
            attempts.append(_attempt_row(idx, rung, ok=True, code=None,
                                         attempt=attempt, policy=rung._applied_policy))
            return True, attempts

    def _adopt_resumed(self, step, resumed, pending) -> None:
        """resume() returns a fresh Step copy; adopt its output onto our step.

        The single charge (cost_usd) set at submit is preserved on the copy; we
        never add a second charge here — that is invariant I5.
        """
        step.assets = list(resumed.assets)
        if resumed.cost_usd is not None:
            step.cost_usd = resumed.cost_usd
        for k, v in (resumed.metadata or {}).items():
            step.metadata.setdefault(k, v)
        step.metadata.pop(PENDING_PREDICTION_KEY, None)
        step.metadata["resumed_from"] = str(pending)

    def generate(self, step, config=None):  # noqa: ANN001
        requested_model = step.model
        requested_rung = self.rungs[0].name
        all_attempts: list[dict[str, Any]] = []

        for idx, rung in enumerate(self.rungs):
            succeeded, attempts = self._attempt_rung(idx, rung, step, config)
            all_attempts.extend(attempts)
            if not succeeded:
                continue
            resumed = step.metadata.get("resumed_from")
            step.metadata[LADDER_META_KEY] = {
                "rung_index": idx,
                "provider": rung.name,
                "model": rung.model,
                "requested_rung": requested_rung,
                "requested_model": requested_model,
                "fell_back": idx > 0,
                "resumed": bool(resumed),
                "retry_policy": rung._applied_policy,
                "rungs_total": len(self.rungs),
                "attempts": all_attempts,
            }
            step.metadata.setdefault("stage", "narration")
            return step

        # every rung exhausted
        raise ProviderError(
            f"all {len(self.rungs)} TTS rungs exhausted "
            f"({' -> '.join(r.name for r in self.rungs)})",
            error_code=ProviderErrorCode.SERVER_ERROR,
        )


def _attempt_row(
    idx: int,
    rung: Rung,
    *,
    ok: bool,
    code: ProviderErrorCode | None,
    attempt: int,
    error: str | None = None,
    retried: bool = False,
    resumed: str | None = None,
    policy: str = "",
) -> dict[str, Any]:
    return {
        "rung_index": idx,
        "provider": rung.name,
        "model": rung.model,
        "ok": ok,
        "attempt": attempt,
        "error_code": _code_value(code),
        "error": error,
        "retried": retried,
        "resumed": resumed,
        "retry_policy": policy,
    }


def ladder_outcome(step) -> dict[str, Any] | None:  # noqa: ANN001
    """Read the ladder provenance note off a completed step (or ``None``)."""
    meta = getattr(step, "metadata", None) or {}
    return meta.get(LADDER_META_KEY)
