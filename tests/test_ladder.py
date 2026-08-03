"""Cross-provider TTS ladder — our OWN try/rung engine (not fallback_models).

The manifest must record the ACTUAL rung that ran (invariant I3):
rung 1 fails -> rung 2 records, and a total collapse fails honestly.
"""

from __future__ import annotations

import pytest
from genblaze_core import Modality, Pipeline
from genblaze_core.exceptions import PipelineError, ProviderError
from genblaze_core.models.enums import ProviderErrorCode
from genblaze_core.models.step import Step
from genblaze_core.providers.base import SyncProvider
from genblaze_core.providers.retry import RetryPolicy

from castiron.db import Database
from castiron.ladder import LadderTTSProvider, Rung, ladder_outcome
from castiron.media import local_asset, synth_tone
from castiron.pipeline import TTS_LADDER, run_offline_episode
from castiron.providers import LocalTTSProvider
from castiron.resume import ResumableTTSProvider


@pytest.fixture
def narration(tmp_path):
    return synth_tone(tmp_path / "n.mp3", seconds=0.5)


def _ladder(narration, *, down: set[int]) -> LadderTTSProvider:
    names = ("elevenlabs", "lmnt", "hume")
    rungs = [
        Rung(
            provider=LocalTTSProvider(narration, name=names[i], should_fail=(i in down)),
            model=TTS_LADDER[i],
            name=names[i],
        )
        for i in range(3)
    ]
    return LadderTTSProvider(rungs)


def _run_one(ladder) -> object:
    result = (
        Pipeline("ladder-test", preflight=False)
        .step(ladder, model=TTS_LADDER[0], prompt="hi", modality=Modality.AUDIO)
        .run(raise_on_failure=False)
    )
    return result.run.steps[0]


def test_happy_records_rung_zero(narration):
    step = _run_one(_ladder(narration, down=set()))
    assert step.status == "succeeded"
    assert step.model == TTS_LADDER[0]
    note = ladder_outcome(step)
    assert note["rung_index"] == 0
    assert note["provider"] == "elevenlabs"
    assert note["fell_back"] is False


def test_rung_one_fails_rung_two_records(narration):
    # rung 0 (elevenlabs) down -> ladder steps to rung 1 (lmnt)
    step = _run_one(_ladder(narration, down={0}))
    assert step.status == "succeeded"
    assert step.model == TTS_LADDER[1] == "lmnt-blizzard"
    note = ladder_outcome(step)
    assert note["rung_index"] == 1
    assert note["provider"] == "lmnt"
    assert note["fell_back"] is True
    # both the failed and the winning attempt are recorded
    assert [a["ok"] for a in note["attempts"]] == [False, True]
    assert note["attempts"][0]["error_code"] == "model_error"


def test_two_rungs_fail_third_records(narration):
    step = _run_one(_ladder(narration, down={0, 1}))
    assert step.status == "succeeded"
    assert step.model == TTS_LADDER[2] == "hume-octave"
    assert ladder_outcome(step)["rung_index"] == 2


def test_all_rungs_exhausted_fails_honestly(narration):
    step = _run_one(_ladder(narration, down={0, 1, 2}))
    assert step.status == "failed"
    assert ladder_outcome(step) is None  # no rung ⇒ no provenance note


def test_all_rungs_exhausted_raises_when_asked(narration):
    with pytest.raises(PipelineError):
        (
            Pipeline("ladder-boom", preflight=False)
            .step(_ladder(narration, down={0, 1, 2}), model=TTS_LADDER[0],
                  prompt="hi", modality=Modality.AUDIO)
            .run(raise_on_failure=True)
        )


def test_ladder_generate_raises_provider_error_directly(narration):
    """Unit-level: the composite provider raises ProviderError when exhausted."""
    from genblaze_core.models.step import Step

    ladder = _ladder(narration, down={0, 1, 2})
    step = Step(provider="castiron-tts-ladder", model=TTS_LADDER[0],
                modality=Modality.AUDIO, prompt="hi")
    with pytest.raises(ProviderError):
        ladder.generate(step)


def test_runner_records_fallback_rung_in_stage(store):
    r = run_offline_episode(store_root=store, run_id="lad", chaos="tts",
                            db=Database(":memory:"))
    narr = r.stage("narration")
    assert narr.fallback_rung == 1
    assert narr.model_used == "lmnt-blizzard"
    assert narr.provider_used == "lmnt"
    assert r.fallback_used is True


# --------------------------------------------------------------------------- #
# P2 resilience depth — retry, transient-resume, callbacks, policy labels
# --------------------------------------------------------------------------- #
def _step() -> Step:
    return Step(provider="castiron-tts-ladder", model=TTS_LADDER[0],
                modality=Modality.AUDIO, prompt="hi")


class _FlakyRung(SyncProvider):
    """Raises a *transient* error (no pending id) ``fail_times`` then succeeds —
    exercises same-rung RETRY (not fallback)."""

    def __init__(self, asset, *, name: str, fail_times: int,
                 code: ProviderErrorCode = ProviderErrorCode.TIMEOUT) -> None:
        super().__init__()
        self.name = name  # type: ignore[assignment]
        self._asset = asset
        self._fail_times = fail_times
        self._code = code
        self.calls = 0

    def generate(self, step, config=None):  # noqa: ANN001
        self.calls += 1
        if self.calls <= self._fail_times:
            raise ProviderError("transient blip (injected)", error_code=self._code)
        step.assets.append(local_asset(self._asset, media_type="audio/mpeg"))
        step.cost_usd = 0.002
        return step


def test_ladder_resumes_transient_prediction_single_charge(narration):
    """A9/I5: a rung that submits (charges) then dies transiently is RESUMED on
    the same rung — one charge, no fallback, provenance records the resume."""
    prov = ResumableTTSProvider(narration, name="elevenlabs", cost_usd=0.002)
    rung = Rung(provider=prov, model="eleven_multilingual_v2", name="elevenlabs")
    seen: list[tuple[int, str, str]] = []
    ladder = LadderTTSProvider(
        [rung], on_resume=lambda i, r, pid: seen.append((i, r.name, pid))
    )
    step = _step()
    out = ladder.generate(step)

    assert out.assets                       # resumed asset adopted
    assert prov.submit_count == 1           # never resubmitted
    assert prov.resume_count == 1
    assert step.cost_usd == pytest.approx(0.002)   # single charge
    assert step.metadata["resumed_from"].startswith("pred-")
    note = ladder_outcome(step)
    assert note["rung_index"] == 0
    assert note["resumed"] is True
    assert note["fell_back"] is False
    # the winning attempt row is the resume, not a resubmit
    assert note["attempts"][-1]["ok"] is True
    assert note["attempts"][-1]["resumed"].startswith("pred-")
    assert len(seen) == 1 and seen[0][1] == "elevenlabs"


def test_ladder_retries_same_rung_then_succeeds(narration):
    """Transient error with NO pending id → RETRY the same rung (aggressive
    policy), fire on_retry, then succeed — no fallback occurs."""
    prov = _FlakyRung(narration, name="elevenlabs", fail_times=2)
    rung = Rung(provider=prov, model="m", name="elevenlabs", retry=RetryPolicy.aggressive())
    retries: list[int] = []
    ladder = LadderTTSProvider([rung], on_retry=lambda i, r, a, e: retries.append(a))
    step = _step()
    ladder.generate(step)

    assert prov.calls == 3                  # 2 failed attempts + 1 success
    assert retries == [1, 2]                # on_retry fired for each retry
    note = ladder_outcome(step)
    assert note["rung_index"] == 0          # stayed on the same rung
    assert note["retry_policy"] == "aggressive"
    assert [a["ok"] for a in note["attempts"]] == [False, False, True]
    assert note["attempts"][0]["retried"] is True
    assert note["attempts"][0]["error_code"] == "timeout"


def test_ladder_fires_on_fallback_callback(narration):
    names = ("elevenlabs", "lmnt")
    rungs = [
        Rung(provider=LocalTTSProvider(narration, name=names[0], should_fail=True),
             model="a", name=names[0]),
        Rung(provider=LocalTTSProvider(narration, name=names[1]), model="b", name=names[1]),
    ]
    fell: list[tuple[int, str]] = []
    ladder = LadderTTSProvider(rungs, on_fallback=lambda i, r, e: fell.append((i, r.name)))
    ladder.generate(_step())
    assert fell == [(0, "elevenlabs")]      # stepped down off rung 0 exactly once


def test_ladder_empty_rungs_rejected():
    with pytest.raises(ValueError):
        LadderTTSProvider([])


def test_ladder_records_custom_retry_policy_label(narration):
    """A RetryPolicy that matches no named preset is labelled custom(...) in the
    manifest provenance note."""
    rung = Rung(provider=LocalTTSProvider(narration, name="elevenlabs"),
                model="m", name="elevenlabs", retry=RetryPolicy(max_attempts=5))
    ladder = LadderTTSProvider([rung])
    step = _step()
    ladder.generate(step)
    assert ladder_outcome(step)["retry_policy"] == "custom(max_attempts=5)"
