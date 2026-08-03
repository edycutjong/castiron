"""AgentLoop narration quality gate (B4) — generate → evaluate → refine.

Proves the gate uses BOTH documented evaluator types, genuinely iterates on the
seeded em-dash pacing flaw (fails once, then passes), threads feedback into the
next iteration, and does NOT iterate on a clean script.
"""

from __future__ import annotations

import pytest
from genblaze_core import (
    CallableEvaluator,
    Modality,
    Pipeline,
    ThresholdEvaluator,
)

from castiron.db import Database
from castiron.gate import (
    GatedNarrationProvider,
    build_gate_evaluator,
    duration_evaluator,
    loudness_silence_evaluator,
    pacing_report,
    run_narration_gate_sync,
)
from castiron.media import synth_tone
from castiron.pipeline import run_offline_episode

# em-dash cluster → the pacing trap the gate must catch (SEED_DATA space_update)
FLAWED = ("Tonight on the space update — and this is where naive TTS trips — the rover "
          "crossed the ridge, paused — for a long dramatic beat — then rolled on.")
CLEAN = ("Tonight on the space update the rover crossed the ridge and rolled on to the "
         "next sample site while the team tracked telemetry from the control room.")


@pytest.fixture
def asset(tmp_path):
    return synth_tone(tmp_path / "n.mp3", seconds=0.5)


def _result(script: str, *, fixed: bool, asset):
    return (
        Pipeline("gate-test", preflight=False)
        .step(GatedNarrationProvider(asset, script, fixed=fixed), model="g",
              prompt=script, modality=Modality.AUDIO)
        .run(raise_on_failure=False)
    )


# --- pacing model is deterministic ------------------------------------------
def test_pacing_report_flaw_then_fixed():
    bad = pacing_report(FLAWED, fixed=False)
    good = pacing_report(FLAWED, fixed=True)
    assert bad.emdash_clusters >= 1
    assert bad.silence_ratio > 0.10          # dead-air out of band
    assert bad.duration_drift > 1.5          # drifts past the threshold
    assert good.silence_ratio <= 0.10 and good.duration_drift <= 1.5


# --- ThresholdEvaluator duration reject (B4) --------------------------------
def test_threshold_evaluator_rejects_duration_drift(asset):
    ev = duration_evaluator(tol=1.5)
    bad = ev.evaluate(_result(FLAWED, fixed=False, asset=asset))
    good = ev.evaluate(_result(FLAWED, fixed=True, asset=asset))
    assert bad.passed is False
    assert "drifts" in (bad.feedback or "")
    assert good.passed is True


def test_callable_evaluator_flags_silence_and_loudness(asset):
    ev = loudness_silence_evaluator()
    bad = ev.evaluate(_result(FLAWED, fixed=False, asset=asset))
    assert bad.passed is False
    assert "silence" in bad.feedback and "LUFS" in bad.feedback


def test_gate_uses_both_evaluator_types():
    gate = build_gate_evaluator()
    kinds = {type(e) for e in gate._evaluators}
    assert CallableEvaluator in kinds
    assert ThresholdEvaluator in kinds


# --- the loop genuinely iterates then passes --------------------------------
def test_gate_iterates_once_then_passes(asset):
    events: list[dict] = []
    r = run_narration_gate_sync(script=FLAWED, asset_path=asset, on_event=events.append)
    assert r.passed is True
    assert r.iterations == 2            # exactly one refinement
    assert r.refinements == 1
    assert r.iterated is True
    # iteration 0 failed, iteration 1 passed
    assert [it.passed for it in r.records] == [False, True]
    # the fix was applied only on the second iteration
    assert [it.fix_applied for it in r.records] == [False, True]
    # feedback from iter 0 was threaded into iter 1 ("started" carries feedback_in)
    started = [e for e in events if e["type"] == "gate.iteration.started"]
    assert started[0]["feedback_in"] is None
    assert started[1]["feedback_in"] and "pacing" in started[1]["feedback_in"].lower()


def test_gate_does_not_iterate_on_clean_script(asset):
    r = run_narration_gate_sync(script=CLEAN, asset_path=asset)
    assert r.passed is True
    assert r.iterations == 1            # no flaw ⇒ no refinement (honest, not a fixed loop)
    assert r.refinements == 0


def test_gate_event_stream_is_ordered(asset):
    events: list[dict] = []
    run_narration_gate_sync(script=FLAWED, asset_path=asset, on_event=events.append)
    types = [e["type"] for e in events]
    assert types == [
        "gate.iteration.started", "gate.iteration.evaluated",
        "gate.iteration.started", "gate.iteration.evaluated",
        "gate.completed",
    ]


# --- integrated through the episode runner ----------------------------------
def test_episode_with_gate_completes_and_summarizes(store):
    r = run_offline_episode(script=FLAWED, gate=True, store_root=store,
                            run_id="gate-ep", db=Database(":memory:"))
    assert r.ok is True
    assert r.gate is not None
    assert r.gate["passed"] is True
    assert r.gate["refinements"] == 1
    assert r.gate["feedback_history"]        # at least one threaded feedback string
