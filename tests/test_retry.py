"""Per-rung RetryPolicy wiring (the reserved ``Rung.retry`` field, now live).

The ladder consults each rung's ``RetryPolicy.should_retry`` for *transient* codes
before stepping down. ``disabled()`` = one attempt (P1-identical); ``conservative()``
retries a transient a couple times; ``aggressive()`` many; and a provider *outage*
(``MODEL_ERROR``) is non-retryable in every preset, so it steps down on the first
try (this is what keeps the P1 chaos ladder byte-identical).
"""

from __future__ import annotations

import pytest
from genblaze_core import Modality, Pipeline
from genblaze_core.models.enums import ProviderErrorCode
from genblaze_core.providers.retry import RetryPolicy

from castiron.ladder import LadderTTSProvider, Rung, ladder_outcome
from castiron.media import synth_tone
from castiron.providers import LocalTTSProvider, failing_provider

TTS = ("eleven", "lmnt", "hume")


@pytest.fixture
def narration(tmp_path):
    return synth_tone(tmp_path / "n.mp3", seconds=0.5)


def _ladder_with_transient_rung0(narration, policy: RetryPolicy,
                                 code=ProviderErrorCode.TIMEOUT) -> LadderTTSProvider:
    """Rung 0 always fails with ``code``; rung 1 succeeds."""
    rungs = [
        Rung(failing_provider(name="eleven", error_code=code),
             model=TTS[0], name="elevenlabs", retry=policy),
        Rung(LocalTTSProvider(narration, name="lmnt"), model=TTS[1], name="lmnt",
             retry=RetryPolicy.disabled()),
    ]
    return LadderTTSProvider(rungs)


def _run(ladder):
    return (
        Pipeline("retry-test", preflight=False)
        .step(ladder, model=TTS[0], prompt="hi", modality=Modality.AUDIO)
        .run(raise_on_failure=False)
    ).run.steps[0]


def _rung0_attempts(step) -> int:
    note = ladder_outcome(step) or {}
    return sum(1 for a in note.get("attempts", []) if a["rung_index"] == 0)


def test_disabled_policy_tries_rung_once(narration):
    step = _run(_ladder_with_transient_rung0(narration, RetryPolicy.disabled()))
    assert _rung0_attempts(step) == 1
    assert step.model == TTS[1]                 # stepped to lmnt


def test_conservative_policy_retries_transient(narration):
    step = _run(_ladder_with_transient_rung0(narration, RetryPolicy.conservative()))
    # conservative.max_attempts == 2 → attempted twice before stepping down
    assert _rung0_attempts(step) == 2
    assert step.model == TTS[1]


def test_aggressive_policy_retries_more(narration):
    step = _run(_ladder_with_transient_rung0(narration, RetryPolicy.aggressive()))
    assert _rung0_attempts(step) == RetryPolicy.aggressive().max_attempts  # 7


def test_model_error_is_not_retried_even_with_conservative(narration):
    """A provider OUTAGE steps down immediately — keeps the P1 chaos path exact."""
    step = _run(_ladder_with_transient_rung0(
        narration, RetryPolicy.conservative(), code=ProviderErrorCode.MODEL_ERROR))
    assert _rung0_attempts(step) == 1
    assert step.model == TTS[1]


def test_applied_policy_recorded_in_manifest_note(narration):
    step = _run(_ladder_with_transient_rung0(narration, RetryPolicy.conservative()))
    note = ladder_outcome(step)
    # the winning rung records which policy it ran under (provenance)
    assert note["retry_policy"] == "disabled"          # rung 1 (lmnt) is disabled
    rung0_rows = [a for a in note["attempts"] if a["rung_index"] == 0]
    assert rung0_rows[0]["retry_policy"] == "conservative"
    assert rung0_rows[0]["retried"] is True
