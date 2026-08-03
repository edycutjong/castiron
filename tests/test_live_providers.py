"""Unit tests for the LIVE vendor providers (castiron/live_providers.py).

These never touch the network: ``httpx`` is monkeypatched so every branch —
success, per-status error mapping, chaos injection, graceful degradation,
ElevenLabs voice iteration/caching, Hume no-audio, OpenAI url fallback — is
exercised deterministically, keeping the offline suite at 100% coverage.
"""

from __future__ import annotations

import base64

import httpx
import pytest
from genblaze_core.exceptions import ProviderError
from genblaze_core.models.enums import ProviderErrorCode
from genblaze_core.models.step import Step

import castiron.live_providers as lp


class FakeResp:
    def __init__(self, status=200, content=b"", json_data=None, text=""):
        self.status_code = status
        self.content = content
        self._json = json_data
        self.text = text or ""

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


def _step(prompt="hello world", model="m"):
    return Step(model=model, prompt=prompt, provider="test")


@pytest.fixture(autouse=True)
def _clear_voice_cache():
    lp._EL_VOICE_CACHE.clear()
    yield
    lp._EL_VOICE_CACHE.clear()


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def test_status_to_code():
    assert lp._status_to_code(429) is ProviderErrorCode.RATE_LIMIT
    assert lp._status_to_code(500) is ProviderErrorCode.SERVER_ERROR
    assert lp._status_to_code(503) is ProviderErrorCode.SERVER_ERROR
    assert lp._status_to_code(402) is ProviderErrorCode.MODEL_ERROR
    assert lp._status_to_code(400) is ProviderErrorCode.MODEL_ERROR


def test_require(monkeypatch):
    monkeypatch.delenv("NOPE_KEY", raising=False)
    with pytest.raises(ProviderError):
        lp._require("NOPE_KEY")
    monkeypatch.setenv("SOME_KEY", "v")
    assert lp._require("SOME_KEY") == "v"


def test_post_http_error_maps_to_server_error(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(lp.httpx, "post", boom)
    monkeypatch.setenv("LMNT_API_KEY", "k")
    prov = lp.LMNTTTSProvider(tmp_path / "o.mp3", name="lmnt", cost_usd=0.02)
    with pytest.raises(ProviderError) as ei:
        prov.generate(_step())
    assert ei.value.error_code is ProviderErrorCode.SERVER_ERROR


# --------------------------------------------------------------------------- #
# chaos + degrade (base _LiveProvider behavior)
# --------------------------------------------------------------------------- #
def test_should_fail_raises_injected(tmp_path):
    prov = lp.LMNTTTSProvider(tmp_path / "o.mp3", name="lmnt", cost_usd=0.02,
                              should_fail=True)
    with pytest.raises(ProviderError) as ei:
        prov.generate(_step())
    assert ei.value.error_code is ProviderErrorCode.MODEL_ERROR


def test_degrade_falls_back_to_existing_fixture(monkeypatch, tmp_path):
    out = tmp_path / "music.mp3"
    out.write_bytes(b"SYNTH-FIXTURE")  # pre-existing offline synth
    monkeypatch.setenv("STABILITY_API_KEY", "k")
    monkeypatch.setattr(lp.httpx, "post", lambda *a, **k: FakeResp(402, text="no credits"))
    prov = lp.make_live_music(out, should_fail=False)
    step = _step()
    prov.generate(step)
    assert step.metadata["degraded"].startswith("stability-audio")
    assert step.cost_usd == 0.0
    assert step.assets and out.read_bytes() == b"SYNTH-FIXTURE"


def test_no_degrade_reraises_when_no_fixture(monkeypatch, tmp_path):
    out = tmp_path / "missing.mp3"  # does not exist
    monkeypatch.setenv("STABILITY_API_KEY", "k")
    monkeypatch.setattr(lp.httpx, "post", lambda *a, **k: FakeResp(500, text="boom"))
    prov = lp.make_live_music(out, should_fail=False)
    with pytest.raises(ProviderError):
        prov.generate(_step())


# --------------------------------------------------------------------------- #
# ElevenLabs (voice discovery, iteration, cache, override, all-fail)
# --------------------------------------------------------------------------- #
def _el_voices(*ids_cats):
    return FakeResp(200, json_data={"voices": [
        {"voice_id": vid, "category": cat} for vid, cat in ids_cats
    ]})


def test_elevenlabs_success_and_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    monkeypatch.setattr(lp.httpx, "get",
                        lambda *a, **k: _el_voices(("v1", "premade"), ("v2", "professional")))
    posts = []

    def fake_post(url, **k):
        posts.append(url)
        return FakeResp(200, content=b"A" * 2048)
    monkeypatch.setattr(lp.httpx, "post", fake_post)
    prov = lp.make_live_tts("elevenlabs", tmp_path / "n.mp3")
    prov.generate(_step())
    assert lp._EL_VOICE_CACHE["k"] == "v1"       # premade preferred + cached
    # second call: cached voice ordered first
    prov.generate(_step())
    assert posts[1].endswith("/v1")


def test_elevenlabs_voice_override(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "custom-voice")

    def no_get(*a, **k):  # override must skip discovery entirely
        raise AssertionError("should not list voices when pinned")
    monkeypatch.setattr(lp.httpx, "get", no_get)
    monkeypatch.setattr(lp.httpx, "post", lambda url, **k: FakeResp(200, content=b"A" * 2048))
    prov = lp.ElevenLabsTTSProvider(tmp_path / "n.mp3", name="elevenlabs", cost_usd=0.03)
    prov.generate(_step())
    assert (tmp_path / "n.mp3").exists()


def test_elevenlabs_all_voices_402_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    monkeypatch.setattr(lp.httpx, "get",
                        lambda *a, **k: _el_voices(("v1", "premade"), ("v2", "premade")))
    monkeypatch.setattr(lp.httpx, "post", lambda *a, **k: FakeResp(402, text="paid only"))
    prov = lp.ElevenLabsTTSProvider(tmp_path / "n.mp3", name="elevenlabs", cost_usd=0.03)
    with pytest.raises(ProviderError):
        prov.generate(_step())


def test_elevenlabs_no_voices_raises_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    monkeypatch.setattr(lp.httpx, "get", lambda *a, **k: _el_voices())  # empty
    prov = lp.ElevenLabsTTSProvider(tmp_path / "n.mp3", name="elevenlabs", cost_usd=0.03)
    with pytest.raises(ProviderError):
        prov.generate(_step())


# --------------------------------------------------------------------------- #
# LMNT / Hume / Stability / OpenAI
# --------------------------------------------------------------------------- #
def test_lmnt_success(monkeypatch, tmp_path):
    monkeypatch.setenv("LMNT_API_KEY", "k")
    monkeypatch.setattr(lp.httpx, "post", lambda *a, **k: FakeResp(200, content=b"A" * 2048))
    prov = lp.make_live_tts("lmnt", tmp_path / "n.mp3")
    prov.generate(_step())
    assert (tmp_path / "n.mp3").read_bytes() == b"A" * 2048


def test_hume_success(monkeypatch, tmp_path):
    monkeypatch.setenv("HUME_API_KEY", "k")
    audio = base64.b64encode(b"HUMEAUDIO").decode()
    monkeypatch.setattr(lp.httpx, "post",
                        lambda *a, **k: FakeResp(200, json_data={"generations": [{"audio": audio}]}))
    prov = lp.make_live_tts("hume", tmp_path / "n.mp3")
    prov.generate(_step())
    assert (tmp_path / "n.mp3").read_bytes() == b"HUMEAUDIO"


def test_hume_no_audio_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("HUME_API_KEY", "k")
    monkeypatch.setattr(lp.httpx, "post",
                        lambda *a, **k: FakeResp(200, json_data={"generations": []}))
    prov = lp.HumeTTSProvider(tmp_path / "n.mp3", name="hume", cost_usd=0.02)
    with pytest.raises(ProviderError):
        prov.generate(_step())


def test_stability_success_reports_model(monkeypatch, tmp_path):
    monkeypatch.setenv("STABILITY_API_KEY", "k")
    monkeypatch.setattr(lp.httpx, "post", lambda *a, **k: FakeResp(200, content=b"M" * 4096))
    prov = lp.make_live_music(tmp_path / "m.mp3")
    step = _step()
    prov.generate(step)
    assert step.model == "stable-audio-2"
    assert step.cost_usd == 0.06


def test_openai_cover_b64(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    b64 = base64.b64encode(b"PNGDATA").decode()
    monkeypatch.setattr(lp.httpx, "post",
                        lambda *a, **k: FakeResp(200, json_data={"data": [{"b64_json": b64}]}))
    prov = lp.make_live_cover(tmp_path / "c.png")
    prov.generate(_step())
    assert (tmp_path / "c.png").read_bytes() == b"PNGDATA"


def test_openai_cover_url_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setattr(lp.httpx, "post",
                        lambda *a, **k: FakeResp(200, json_data={"data": [{"url": "http://img/x.png"}]}))
    monkeypatch.setattr(lp.httpx, "get", lambda *a, **k: FakeResp(200, content=b"URLPNG"))
    prov = lp.OpenAIImageCoverProvider(tmp_path / "c.png", name="openai-image", cost_usd=0.05)
    prov.generate(_step())
    assert (tmp_path / "c.png").read_bytes() == b"URLPNG"


# --------------------------------------------------------------------------- #
# factories
# --------------------------------------------------------------------------- #
def test_factories(tmp_path):
    assert isinstance(lp.make_live_tts("elevenlabs", tmp_path / "a"), lp.ElevenLabsTTSProvider)
    assert isinstance(lp.make_live_tts("lmnt", tmp_path / "b"), lp.LMNTTTSProvider)
    assert isinstance(lp.make_live_tts("hume", tmp_path / "c"), lp.HumeTTSProvider)
    assert isinstance(lp.make_live_music(tmp_path / "d"), lp.StabilityMusicProvider)
    assert isinstance(lp.make_live_cover(tmp_path / "e"), lp.OpenAIImageCoverProvider)


# --------------------------------------------------------------------------- #
# pipeline LIVE branches (settings.offline == False)
# --------------------------------------------------------------------------- #
def test_make_rung_live_returns_vendor_providers(tmp_path):
    from genblaze_core.providers.retry import RetryPolicy

    from castiron.chaos import resolve_chaos
    from castiron.pipeline import _make_rung
    narr = tmp_path / "n.mp3"
    narr.write_bytes(b"x")
    spec = resolve_chaos(None)
    assert isinstance(_make_rung(0, narr, spec, RetryPolicy.disabled(), live=True).provider,
                      lp.ElevenLabsTTSProvider)
    assert isinstance(_make_rung(1, narr, spec, RetryPolicy.disabled(), live=True).provider,
                      lp.LMNTTTSProvider)
    assert isinstance(_make_rung(2, narr, spec, RetryPolicy.disabled(), live=True).provider,
                      lp.HumeTTSProvider)


def test_build_episode_pipeline_live_branch(tmp_path, monkeypatch):
    import castiron.pipeline as pl
    from castiron.backends import LocalDirBackend
    from castiron.config import Settings
    live = Settings(offline=False, local_store=tmp_path, media_bucket="m",
                    published_bucket="p", max_run_cost_usd=1.5)
    monkeypatch.setattr(pl, "settings", live)
    monkeypatch.setattr(pl, "make_media_backend",
                        lambda base, **k: LocalDirBackend(base / "b2" / "m"))
    narr, music, cover = tmp_path / "n.mp3", tmp_path / "mu.mp3", tmp_path / "c.png"
    for p in (narr, music, cover):
        p.write_bytes(b"x")
    pipe, sink, backend = pl.build_episode_pipeline(
        tmp_path, narr, music, cover, script="hi")
    assert pipe is not None and sink is not None
