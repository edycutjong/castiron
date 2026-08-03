"""OFFLINE episode pipeline — the P0 exit-test behaviors, as pytest."""

from __future__ import annotations

import json

import pytest

from castiron.media import extract_manifest, verify_file
from castiron.pipeline import TTS_LADDER, run_offline_episode
from castiron.providers import failing_provider


def test_happy_path_produces_verified_episode(store):
    r = run_offline_episode(store_root=store, run_id="happy")
    assert r.ok
    assert r.manifest_verified
    assert r.episode_verified
    assert r.embed_method == "inline"  # true in-file ID3 manifest, not a sidecar
    assert r.cost_usd > 0
    assert not r.fallback_used
    assert r.model_used == TTS_LADDER[0]


def test_stored_objects_present(store):
    r = run_offline_episode(store_root=store, run_id="objs")
    assert any(k.endswith("manifest.json") for k in r.object_keys)
    assert any(k.endswith(".mp3") for k in r.object_keys)


def test_chaos_forces_fallback_rung(store):
    r = run_offline_episode(store_root=store, run_id="chaos", chaos="tts")
    assert r.fallback_used
    assert r.model_requested == TTS_LADDER[0]
    # the ACTUAL rung used is recorded (I3: fallbacks never hidden)
    assert r.model_used == TTS_LADDER[1]
    assert r.ok


def test_episode_manifest_extract_roundtrips(store):
    r = run_offline_episode(store_root=store, run_id="rt")
    manifest = extract_manifest(r.episode_path)
    assert manifest.canonical_hash == r.manifest_hash
    assert manifest.verify()


def test_manifest_tamper_is_detected(store):
    from mutagen.id3 import ID3

    r = run_offline_episode(store_root=store, run_id="tamper")
    ep = r.episode_path
    tags = ID3(ep)
    frame = tags.get("TXXX:genblaze:manifest")
    doc = json.loads(frame.text[0])
    doc["run"]["steps"][0]["prompt"] = "TAMPERED"
    frame.text = [json.dumps(doc)]
    tags.save(ep)
    assert verify_file(ep) is False
    assert extract_manifest(ep).verify_hash() is False


def test_failing_provider_injection_raises(store):
    """The spec's FailingProvider (MockProvider should_fail) surfaces the error."""
    from genblaze_core import Modality, Pipeline
    from genblaze_core.exceptions import PipelineError

    with pytest.raises(PipelineError):
        Pipeline("boom").step(
            failing_provider(message="ElevenLabs outage (injected)"),
            model="mock", prompt="x", modality=Modality.AUDIO,
        ).run(raise_on_failure=True)


def test_failing_provider_observable_without_raise(store):
    from genblaze_core import Modality, Pipeline

    result = Pipeline("boom2").step(
        failing_provider(), model="mock", prompt="x", modality=Modality.AUDIO,
    ).run(raise_on_failure=False)
    step = result.run.steps[0]
    assert result.run.status == "failed"
    assert step.status == "failed"
    assert step.error
