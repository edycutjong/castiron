"""P1 parallel fan-out: narration + music + cover complete via arun(mc=3)."""

from __future__ import annotations

from castiron.db import Database
from castiron.media import extract_manifest
from castiron.pipeline import STAGE_ORDER, run_offline_episode


def test_three_stages_complete_in_parallel(store):
    r = run_offline_episode(store_root=store, run_id="fan", db=Database(":memory:"))
    assert r.state == "completed"
    assert r.ok
    # all three stages present and succeeded
    assert [s.name for s in r.stages] == list(STAGE_ORDER)
    assert all(s.state == "succeeded" for s in r.stages)


def test_fanout_uses_distinct_providers(store):
    r = run_offline_episode(store_root=store, run_id="fan2", db=Database(":memory:"))
    provs = {s.name: s.provider_used for s in r.stages}
    assert provs["narration"] == "elevenlabs"  # rung 0 on the happy path
    assert provs["music"] == "stability-audio"
    assert provs["cover"] == "gmi-flux"


def test_fanout_lands_all_assets_plus_manifest(store):
    r = run_offline_episode(store_root=store, run_id="fan3", db=Database(":memory:"))
    keys = r.object_keys
    assert sum(k.endswith(".mp3") for k in keys) == 2  # narration + music
    assert sum(k.endswith(".png") for k in keys) == 1  # cover
    assert any(k.endswith("manifest.json") for k in keys)


def test_fanout_manifest_records_three_steps(store):
    r = run_offline_episode(store_root=store, run_id="fan4", db=Database(":memory:"))
    manifest = extract_manifest(r.episode_path)
    steps = manifest.model_dump().get("run", {}).get("steps", [])
    assert len(steps) == 3
    models = {s["model"] for s in steps}
    assert {"elevenlabs-multilingual-v2", "stable-audio-2", "flux-1-schnell"} <= models


def test_fanout_cost_is_sum_of_stage_costs(store):
    r = run_offline_episode(store_root=store, run_id="fan5", db=Database(":memory:"))
    # 0.002 narration + 0.004 music + 0.003 cover
    assert abs(r.cost_usd - 0.009) < 1e-6


def test_fanout_event_stream_has_three_starts_and_completes(store):
    r = run_offline_episode(store_root=store, run_id="fan6", db=Database(":memory:"))
    ev = r.event_types
    assert ev[0] == "pipeline.started"
    assert ev[-1] == "pipeline.completed"
    assert ev.count("step.started") == 3
    assert ev.count("step.completed") == 3
