"""Chaos switch (E12) — the demo control surface for fault injection.

The kill-switch demo turns on a fault and shows the pipeline heal rather than
drop the episode. This module formalizes that switch as a single, parseable
control string so the console, the API, ``verify_offline.py`` and the chaos
matrix all speak the same language:

    CHAOS_FAIL=<provider>[:stage][:timing]

Examples (all accepted by :func:`parse_chaos`)::

    elevenlabs                     # kill the ElevenLabs rung  (stage=narration, timing=immediate)
    tts                            # alias: kill the primary TTS rung
    elevenlabs:narration:transient # ElevenLabs dies mid-generation, then RESUMES (A9)
    narration:transient            # generic narration transient → resume single-charge
    lmnt                           # kill rungs 0..1 (elevenlabs+lmnt) → hume ships
    hume                           # kill all three narration rungs → honest DEGRADED
    stability  / music             # kill the music stage
    gmi        / cover             # kill the cover stage
    budget                         # force the MAX_RUN_COST_USD projection over cap → BUDGET_ABORT

Legacy P1 single-token forms (``tts``/``narration``/``music``/``cover``/``lmnt``/
``hume``) keep their exact P1 meaning, so nothing downstream of P1 changes.

``CHAOS_FAIL`` (env) is read by the app at request time; an explicit ``chaos``
argument to the pipeline always wins over the env so tests stay hermetic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# provider token → the stage it belongs to
_PROVIDER_STAGE = {
    "elevenlabs": "narration",
    "lmnt": "narration",
    "hume": "narration",
    "tts": "narration",
    "stability": "music",
    "gmi": "cover",
    "dalle": "cover",
}
_STAGE_TOKENS = {"narration", "music", "cover"}
_TIMINGS = {"immediate", "mid-stream", "transient"}
# how far down the narration ladder a provider token forces failure
_LADDER_DEPTH = {"tts": 0, "elevenlabs": 0, "lmnt": 1, "hume": 2}


@dataclass(frozen=True)
class ChaosSpec:
    """A parsed fault-injection request.

    Attributes:
        provider: vendor/rung token (``elevenlabs``/``lmnt``/``hume``/``tts``/
            ``stability``/``gmi``) or ``budget``; ``None`` when only a stage was
            named or no chaos is requested.
        stage: ``narration``/``music``/``cover`` the fault targets; ``None`` when
            no chaos is requested.
        timing: ``immediate`` (default), ``mid-stream`` or ``transient``.
        raw: the original control string (for logging / the manifest note).
    """

    provider: str | None = None
    stage: str | None = None
    timing: str = "immediate"
    raw: str | None = None

    @property
    def active(self) -> bool:
        return self.stage is not None or self.provider == "budget"

    @property
    def is_transient(self) -> bool:
        return self.timing == "transient"

    @property
    def is_budget(self) -> bool:
        return self.provider == "budget"

    def hits_stage(self, stage: str) -> bool:
        """True if this fault targets ``stage`` (music/cover are all-or-nothing)."""
        return self.active and self.stage == stage

    def to_token(self) -> str:
        """Compact label for events/manifest (``provider:stage:timing``)."""
        if not self.active:
            return "none"
        if self.provider == "budget":
            return f"budget:{self.timing}"
        if self.provider is None:  # generic stage fault
            return f"{self.stage}:{self.timing}"
        return f"{self.provider}:{self.stage}:{self.timing}"


NO_CHAOS = ChaosSpec()


def parse_chaos(value: str | None) -> ChaosSpec:
    """Parse a ``CHAOS_FAIL``-style control string into a :class:`ChaosSpec`.

    Tolerant by design (a demo control surface): unknown tokens degrade to "no
    chaos" rather than raising, so a fat-fingered toggle never crashes a run.
    """
    if not value:
        return NO_CHAOS
    raw = value.strip()
    if not raw or raw.lower() in {"none", "off", "false", "0"}:
        return NO_CHAOS

    parts = [p.strip().lower() for p in raw.split(":") if p.strip()]
    head = parts[0]
    rest = parts[1:]
    # Classify trailing fields by token TYPE, not position, so both
    # ``narration:transient`` (stage:timing) and
    # ``elevenlabs:narration:transient`` (provider:stage:timing) parse correctly.
    stage_part = next((p for p in rest if p in _STAGE_TOKENS), None)
    timing_part = next((p for p in rest if p in _TIMINGS), None)

    if head == "budget":
        return ChaosSpec(provider="budget", stage=None,
                         timing=_norm_timing(timing_part), raw=raw)

    provider: str | None
    stage: str | None
    if head in _PROVIDER_STAGE:
        provider = head
        stage = stage_part or _PROVIDER_STAGE[head]
    elif head in _STAGE_TOKENS:
        provider = None
        stage = head
    else:
        # unknown head token → treat as inert (honest no-op, logged upstream)
        return NO_CHAOS

    if stage not in _STAGE_TOKENS:  # pragma: no cover - defensive; stage is always a valid token here
        stage = _PROVIDER_STAGE.get(provider or "", "narration")
    return ChaosSpec(provider=provider, stage=stage,
                     timing=_norm_timing(timing_part), raw=raw)


def _norm_timing(timing: str | None) -> str:
    if timing in _TIMINGS:
        return timing
    return "immediate"


def chaos_from_env() -> ChaosSpec:
    """Read the ``CHAOS_FAIL`` environment variable (the console demo toggle)."""
    return parse_chaos(os.environ.get("CHAOS_FAIL"))


def resolve_chaos(chaos: str | ChaosSpec | None) -> ChaosSpec:
    """Resolve a caller argument to a :class:`ChaosSpec`.

    Explicit argument wins; ``None`` falls back to ``CHAOS_FAIL`` env so the
    console/CLI can drive fault injection while tests stay hermetic by passing an
    explicit value (including ``""`` to force "no chaos").
    """
    if isinstance(chaos, ChaosSpec):
        return chaos
    if chaos is None:
        return chaos_from_env()
    return parse_chaos(chaos)


def narration_rung_down(spec: ChaosSpec, rung_index: int) -> bool:
    """Is narration ladder rung ``rung_index`` forced down by ``spec``?

    Mirrors the P1 ``_rung_down`` truth table exactly for the legacy tokens:
    ``tts``/``elevenlabs`` → rung 0; ``lmnt`` → rungs 0-1; ``hume`` → 0-2;
    a generic ``narration`` fault (no provider) → the whole ladder collapses.
    Transient faults never force a rung *down* — they resume (see A9).
    """
    if not spec.hits_stage("narration") or spec.is_transient:
        return False
    if spec.provider is None:  # generic narration collapse (drop-path test)
        return True
    depth = _LADDER_DEPTH.get(spec.provider)
    if depth is None:
        return False
    return rung_index <= depth


__all__ = [
    "NO_CHAOS",
    "ChaosSpec",
    "chaos_from_env",
    "narration_rung_down",
    "parse_chaos",
    "resolve_chaos",
]
