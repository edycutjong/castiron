"""LIVE vendor providers — the real generative-media engine (P2+).

OFFLINE mode uses the deterministic mock providers in ``castiron.providers``
(local ffmpeg-synthesized bytes, zero network). LIVE mode (B2 creds present and
``OFFLINE`` unset) swaps in the providers below, which make **real** vendor API
calls and write the returned bytes into the run's scratch file so the rest of the
pipeline (manifest → sink → verify → embed → publish) is byte-for-byte identical
to the OFFLINE path — only the source of the media changes.

Each provider is a genblaze ``SyncProvider`` and honors the same ``should_fail``
chaos flag the mocks do, so the cross-provider ladder and the chaos demos behave
identically LIVE: an injected (or real) rung outage raises ``ProviderError`` and
the ladder steps down to the next real vendor.

Confirmed request shapes (probed live against each account):
- ElevenLabs  POST /v1/text-to-speech/{voice}          model eleven_multilingual_v2
- LMNT        POST /v1/ai/speech/bytes                  voice amy · model blizzard · language en
- Hume        POST /v0/tts                              Octave; generations[0].audio (base64)
- Stability   POST /v2beta/audio/stable-audio-2/…       multipart; steps 30 · output mp3
- OpenAI      POST /v1/images/generations               gpt-image-1; data[0].b64_json
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

import httpx
from genblaze_core.exceptions import ProviderError
from genblaze_core.models.enums import ProviderErrorCode
from genblaze_core.providers.base import SyncProvider

from castiron.media import local_asset

_TTS_TEXT_CAP = 5000  # keep a single synth well within free-tier character limits


def _status_to_code(status: int) -> ProviderErrorCode:
    """Map an HTTP status to a ladder-meaningful error code.

    429/5xx are transient (retry-eligible, then step down); everything else
    (402 plan limits, 401/403 auth, 400 bad request) is a hard rung outage that
    steps the ladder down on the first try — exactly like an injected MODEL_ERROR.
    """
    if status == 429:
        return ProviderErrorCode.RATE_LIMIT
    if status >= 500:
        return ProviderErrorCode.SERVER_ERROR
    return ProviderErrorCode.MODEL_ERROR


def _require(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise ProviderError(
            f"{key} not set — rung unavailable",
            error_code=ProviderErrorCode.MODEL_ERROR,
        )
    return val


class _LiveProvider(SyncProvider):
    """Base for LIVE vendor providers: chaos gate + write-bytes-and-emit-asset.

    ``degrade``: single-provider stages (music, cover) have no failover ladder, so
    a *real* vendor error (e.g. out of credits) falls back to the pre-synthesized
    local fixture already at ``out_path`` and ships the episode DEGRADED rather
    than dropping it — CastIron's "the show still ships" thesis. The degradation
    is recorded in ``step.metadata["degraded"]`` (never hidden). An *injected*
    chaos outage (``should_fail``) still raises, so chaos demos fail as intended.
    """

    _stage = "asset"
    _media_type = "application/octet-stream"

    def __init__(
        self,
        out_path: Path,
        *,
        name: str,
        cost_usd: float,
        should_fail: bool = False,
        error_message: str = "provider unavailable (injected)",
        timeout: float = 180.0,
        degrade: bool = False,
        report_model: str | None = None,
    ) -> None:
        super().__init__()
        self.name = name  # type: ignore[assignment]
        self._out = Path(out_path)
        self._cost = cost_usd
        self._should_fail = should_fail
        self._error_message = error_message
        self._timeout = timeout
        self._degrade = degrade
        self._report_model = report_model

    # subclasses return the raw media bytes for the given prompt/text
    def _synthesize(self, text: str, step: Any) -> bytes:  # pragma: no cover - abstract
        raise NotImplementedError

    def generate(self, step, config=None):  # noqa: ANN001
        if self._should_fail:
            # Injected outage (chaos): same typed error the mock raises, so the
            # ladder steps down and the manifest records an identical attempt row.
            raise ProviderError(
                self._error_message, error_code=ProviderErrorCode.MODEL_ERROR
            )
        text = (getattr(step, "prompt", None) or "").strip()[:_TTS_TEXT_CAP]
        degraded: str | None = None
        try:
            data = self._synthesize(text, step)
            self._out.parent.mkdir(parents=True, exist_ok=True)
            self._out.write_bytes(data)
        except ProviderError:
            # No fixture to fall back to, or degradation disabled → propagate
            # (narration rungs re-raise so the ladder steps down).
            if not (self._degrade and self._out.is_file()):
                raise
            degraded = f"{self.name}-unavailable→offline-synth"
        step.assets.append(local_asset(self._out, media_type=self._media_type))
        step.cost_usd = 0.0 if degraded else self._cost
        if self._report_model:
            step.model = self._report_model
        step.metadata.setdefault("stage", self._stage)
        if degraded:
            step.metadata["degraded"] = degraded
        return step

    # shared HTTP helper: raise a ladder-meaningful ProviderError on any non-2xx
    def _post(self, url: str, **kw: Any) -> httpx.Response:
        try:
            r = httpx.post(url, timeout=self._timeout, **kw)
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"{self.name} request failed: {exc}",
                error_code=ProviderErrorCode.SERVER_ERROR,
            ) from exc
        if r.status_code >= 400:
            snippet = r.text[:180].replace("\n", " ")
            raise ProviderError(
                f"{self.name} HTTP {r.status_code}: {snippet}",
                error_code=_status_to_code(r.status_code),
            )
        return r


# --------------------------------------------------------------------------- #
# Narration rungs (TTS) — one real vendor each
# --------------------------------------------------------------------------- #
_EL_VOICE_CACHE: dict[str, str] = {}


def _elevenlabs_voices(api_key: str) -> list[str]:
    """Ordered candidate voice ids: premade first (free-usable), then the rest.

    Free plans 402 on library/professional voices, so we prefer ``premade`` and
    fall through candidates until one synthesizes. ``ELEVENLABS_VOICE_ID`` pins one.
    """
    override = os.environ.get("ELEVENLABS_VOICE_ID")
    if override:
        return [override]
    r = httpx.get(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": api_key},
        timeout=30,
    )
    r.raise_for_status()
    voices = r.json().get("voices", [])
    premade = [v["voice_id"] for v in voices if v.get("category") == "premade"]
    others = [v["voice_id"] for v in voices if v.get("category") != "premade"]
    return premade + others


class ElevenLabsTTSProvider(_LiveProvider):
    _stage = "narration"
    _media_type = "audio/mpeg"

    def _synthesize(self, text: str, step: Any) -> bytes:
        api_key = _require("ELEVENLABS_API_KEY")
        model = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
        # Try the last known-good voice first, then walk premade candidates so a
        # per-voice 402 (paid-only voice) doesn't fail the whole rung.
        candidates = _elevenlabs_voices(api_key)
        cached = _EL_VOICE_CACHE.get(api_key)
        if cached:
            candidates = [cached] + [v for v in candidates if v != cached]
        last: ProviderError | None = None
        for voice in candidates:
            try:
                r = self._post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                    headers={"xi-api-key": api_key},
                    json={"text": text or "CastIron.", "model_id": model},
                )
            except ProviderError as exc:
                last = exc
                continue
            _EL_VOICE_CACHE[api_key] = voice
            return r.content
        raise last or ProviderError(
            "no usable ElevenLabs voice", error_code=ProviderErrorCode.MODEL_ERROR
        )


class LMNTTTSProvider(_LiveProvider):
    _stage = "narration"
    _media_type = "audio/mpeg"

    def _synthesize(self, text: str, step: Any) -> bytes:
        api_key = _require("LMNT_API_KEY")
        r = self._post(
            "https://api.lmnt.com/v1/ai/speech/bytes",
            headers={"X-API-Key": api_key},
            json={
                "text": text or "CastIron.",
                "voice": os.environ.get("LMNT_VOICE", "amy"),
                "model": os.environ.get("LMNT_MODEL", "blizzard"),
                "language": os.environ.get("LMNT_LANGUAGE", "en"),
                "format": "mp3",
            },
        )
        return r.content


class HumeTTSProvider(_LiveProvider):
    _stage = "narration"
    _media_type = "audio/mpeg"

    def _synthesize(self, text: str, step: Any) -> bytes:
        api_key = _require("HUME_API_KEY")
        r = self._post(
            "https://api.hume.ai/v0/tts",
            headers={"X-Hume-Api-Key": api_key, "Content-Type": "application/json"},
            json={"utterances": [{"text": text or "CastIron."}]},
        )
        gens = r.json().get("generations") or []
        if not gens or not gens[0].get("audio"):
            raise ProviderError(
                "Hume returned no audio", error_code=ProviderErrorCode.SERVER_ERROR
            )
        return base64.b64decode(gens[0]["audio"])


# --------------------------------------------------------------------------- #
# Music (Stability stable-audio-2) + Cover (OpenAI gpt-image-1)
# --------------------------------------------------------------------------- #
class StabilityMusicProvider(_LiveProvider):
    _stage = "music"
    _media_type = "audio/mpeg"

    def _synthesize(self, text: str, step: Any) -> bytes:
        api_key = _require("STABILITY_API_KEY")
        model = os.environ.get("STABILITY_AUDIO_MODEL", "stable-audio-2")
        r = self._post(
            f"https://api.stability.ai/v2beta/audio/{model}/text-to-audio",
            headers={"Authorization": f"Bearer {api_key}", "Accept": "audio/*"},
            files={"none": (None, "")},
            data={
                "prompt": text or "ambient instrumental bed",
                "duration": os.environ.get("STABILITY_MUSIC_DURATION", "10"),
                "output_format": "mp3",
                "steps": os.environ.get("STABILITY_MUSIC_STEPS", "30"),
            },
        )
        return r.content


class OpenAIImageCoverProvider(_LiveProvider):
    _stage = "cover"
    _media_type = "image/png"

    def _synthesize(self, text: str, step: Any) -> bytes:
        api_key = _require("OPENAI_API_KEY")
        model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
        size = os.environ.get("OPENAI_IMAGE_SIZE", "1024x1024")
        r = self._post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "prompt": text or "podcast cover art", "n": 1, "size": size},
        )
        item = r.json()["data"][0]
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        # dall-e style url response fallback
        img = httpx.get(item["url"], timeout=self._timeout)
        img.raise_for_status()
        return img.content


# --------------------------------------------------------------------------- #
# Factories (used by the pipeline when settings.offline is False)
# --------------------------------------------------------------------------- #
_TTS_BY_RUNG: dict[str, type[_LiveProvider]] = {
    "elevenlabs": ElevenLabsTTSProvider,
    "lmnt": LMNTTTSProvider,
    "hume": HumeTTSProvider,
}
_TTS_COST = {"elevenlabs": 0.03, "lmnt": 0.02, "hume": 0.02}


def make_live_tts(rung_name: str, out_path: Path, *, should_fail: bool = False) -> _LiveProvider:
    cls = _TTS_BY_RUNG[rung_name]
    return cls(
        out_path,
        name=rung_name,
        cost_usd=_TTS_COST.get(rung_name, 0.03),
        should_fail=should_fail,
        error_message="TTS provider unavailable (injected)",
        timeout=90.0,
    )


def make_live_music(out_path: Path, *, should_fail: bool = False) -> _LiveProvider:
    return StabilityMusicProvider(
        out_path, name="stability-audio", cost_usd=0.06,
        should_fail=should_fail, error_message="music provider unavailable (injected)",
        degrade=True, report_model=os.environ.get("STABILITY_AUDIO_MODEL", "stable-audio-2"),
    )


def make_live_cover(out_path: Path, *, should_fail: bool = False) -> _LiveProvider:
    return OpenAIImageCoverProvider(
        out_path, name="openai-image", cost_usd=0.05,
        should_fail=should_fail, error_message="cover provider unavailable (injected)",
        degrade=True, report_model=os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
    )


__all__ = [
    "ElevenLabsTTSProvider",
    "HumeTTSProvider",
    "LMNTTTSProvider",
    "OpenAIImageCoverProvider",
    "StabilityMusicProvider",
    "make_live_cover",
    "make_live_music",
    "make_live_tts",
]
