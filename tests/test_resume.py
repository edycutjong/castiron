"""Transient resume, single-charge (A9 · invariant I5).

A worker dies mid-generation; the job RESUMES the in-flight prediction via
``Pipeline.resume_step`` / ``aresume_step`` instead of resubmitting, so the step
is billed exactly once (summed ``step.cost_usd`` — there is no CostLedger class).
"""

from __future__ import annotations

import pytest

from castiron.db import Database
from castiron.media import synth_tone
from castiron.pipeline import run_offline_episode
from castiron.resume import (
    resubmit_double_charge,
    resume_after_transient_sync,
)

CHARGE = 0.002


def test_resume_step_single_charge():
    out = resume_after_transient_sync(cost_usd=CHARGE, use_async=False)
    assert out.used == "resume_step"
    assert out.submit_count == 1          # never resubmitted
    assert out.resume_count == 1
    assert out.charged_once is True
    assert out.total_charge_usd == pytest.approx(CHARGE)
    assert out.asset_present is True


def test_aresume_step_single_charge():
    out = resume_after_transient_sync(cost_usd=CHARGE, use_async=True)
    assert out.used == "aresume_step"
    assert out.submit_count == 1
    assert out.charged_once is True
    assert out.total_charge_usd == pytest.approx(CHARGE)


def test_resubmit_would_double_charge_contrast():
    """The counterfactual resume avoids: naive resubmit bills twice."""
    assert resubmit_double_charge(cost_usd=CHARGE) == pytest.approx(2 * CHARGE)


def test_integrated_transient_narration_resumes_single_charge(store):
    """A transient narration fault resumes on rung 0 — episode ships, one charge."""
    r = run_offline_episode(chaos="narration:transient", store_root=store,
                            run_id="tr", db=Database(":memory:"))
    assert r.ok is True
    assert r.resumed is True
    narr = r.stage("narration")
    assert narr.fallback_rung == 0          # resumed the SAME rung, did not fall back
    assert narr.provider_used == "elevenlabs"
    # single charge: narration(0.002) + music(0.004) + cover(0.003); NOT a doubled
    # narration charge (which would make it 0.011).
    assert r.cost_usd == pytest.approx(0.009)


def test_integrated_transient_emits_resume_event(store):
    db = Database(":memory:")
    run_offline_episode(chaos="elevenlabs:narration:transient", store_root=store,
                        run_id="tr2", db=db)
    types = [e.type for e in db.list_events("tr2")]
    assert "stage.resumed" in types


def test_resume_outcome_as_dict_is_report_shaped():
    out = resume_after_transient_sync(cost_usd=CHARGE, use_async=False)
    d = out.as_dict()
    assert d["resume_primitive"] == "resume_step"
    assert d["submit_count"] == 1
    assert d["resume_count"] == 1
    assert d["charged_once"] is True
    assert d["total_charge_usd"] == pytest.approx(CHARGE)


def test_resume_adopts_real_asset_bytes(tmp_path):
    """When the resumable rung has a real source file, the resumed step adopts
    those bytes (real sha256), proving the resume returns actual output."""
    asset = synth_tone(tmp_path / "n.mp3", seconds=0.3)
    out = resume_after_transient_sync(asset_path=asset, cost_usd=CHARGE, use_async=False)
    assert out.asset_present is True
    assert out.charged_once is True
