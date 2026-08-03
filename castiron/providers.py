"""CastIron providers for the OFFLINE path + failure injection.

Two spec-vs-SDK realities pinned at build (see DEVIATIONS.md / friction-log):
- genblaze 0.4.1 ships **no** ``FailingProvider``/``ModelErrorProvider`` classes.
  The documented failure-injection primitive is ``MockProvider(should_fail=True,
  error_code=...)``. ``failing_provider()`` is the named shim the spec assumes.
- ``ProviderErrorCode`` members are: TIMEOUT, RATE_LIMIT, AUTH_FAILURE,
  INVALID_INPUT, MODEL_ERROR, SERVER_ERROR, CONTENT_POLICY, UNKNOWN
  (there is no ``PROVIDER_ERROR``).

The OFFLINE providers here emit **real bytes** (ffmpeg-synthesized audio/PNG)
so the manifest/sink/verify chain runs end-to-end with zero network. In LIVE
mode these are swapped for the real vendor providers (ElevenLabs / LMNT / Hume
for TTS, Stability for music, GMI FLUX / DALL·E for cover).
"""

from __future__ import annotations

from pathlib import Path

from genblaze_core.exceptions import ProviderError
from genblaze_core.models.enums import ProviderErrorCode
from genblaze_core.providers.base import SyncProvider
from genblaze_core.testing import MockProvider

from castiron.media import local_asset


def failing_provider(
    *,
    name: str = "failing",
    error_code: ProviderErrorCode = ProviderErrorCode.SERVER_ERROR,
    message: str = "provider outage (injected)",
) -> MockProvider:
    """The spec's ``FailingProvider`` realized on the real SDK.

    ``MockProvider(should_fail=True)`` raises ``ProviderError`` on every
    ``generate()`` — the failure-injection primitive genblaze actually ships.
    """
    return MockProvider(
        name=name,
        should_fail=True,
        error_code=error_code,
        error_message=message,
    )


class _LocalAssetProvider(SyncProvider):
    """Base for OFFLINE providers that emit one pre-synthesized local asset.

    Emits a real ``file://`` asset (real sha256) and records ``cost_usd`` and a
    ``stage`` tag in ``step.metadata`` so the stage machine can label the step.
    Set ``should_fail`` to raise a typed ``ProviderError`` (chaos injection).
    """

    _stage = "asset"

    def __init__(
        self,
        asset_path: Path,
        *,
        name: str,
        media_type: str,
        cost_usd: float = 0.001,
        should_fail: bool = False,
        error_code: ProviderErrorCode = ProviderErrorCode.SERVER_ERROR,
        error_message: str = "provider outage (injected)",
    ) -> None:
        super().__init__()
        self.name = name  # type: ignore[assignment]
        self._asset_path = Path(asset_path)
        self._media_type = media_type
        self._cost_usd = cost_usd
        self._should_fail = should_fail
        self._error_code = error_code
        self._error_message = error_message

    def generate(self, step, config=None):  # noqa: ANN001
        if self._should_fail:
            raise ProviderError(self._error_message, error_code=self._error_code)
        step.assets.append(local_asset(self._asset_path, media_type=self._media_type))
        step.cost_usd = self._cost_usd
        step.metadata.setdefault("stage", self._stage)
        return step


class LocalTTSProvider(_LocalAssetProvider):
    """OFFLINE TTS stand-in emitting a real local audio asset.

    Two failure modes for chaos:
    - ``should_fail=True`` — the provider itself is down (a whole ladder rung);
      raises ``MODEL_ERROR`` so the cross-provider ladder steps to the next rung.
    - ``unavailable={model, ...}`` — model-sensitive: raises for those models
      (used by the legacy single-step ``fallback_models`` demonstration).
    """

    _stage = "narration"

    def __init__(
        self,
        audio_path: Path,
        *,
        name: str = "local-tts",
        unavailable: frozenset[str] = frozenset(),
        media_type: str = "audio/mpeg",
        cost_usd: float = 0.002,
        should_fail: bool = False,
        error_code: ProviderErrorCode = ProviderErrorCode.MODEL_ERROR,
        error_message: str = "TTS provider unavailable (injected)",
    ) -> None:
        super().__init__(
            audio_path,
            name=name,
            media_type=media_type,
            cost_usd=cost_usd,
            should_fail=should_fail,
            error_code=error_code,
            error_message=error_message,
        )
        self._unavailable = set(unavailable)

    def generate(self, step, config=None):  # noqa: ANN001
        if step.model in self._unavailable:
            raise ProviderError(
                f"model {step.model!r} unavailable (injected)",
                error_code=ProviderErrorCode.MODEL_ERROR,
            )
        return super().generate(step, config)


class MockMusicProvider(_LocalAssetProvider):
    """OFFLINE music-bed stand-in (Stability-Audio-shaped)."""

    _stage = "music"

    def __init__(
        self,
        audio_path: Path,
        *,
        name: str = "stability-audio",
        media_type: str = "audio/mpeg",
        cost_usd: float = 0.004,
        should_fail: bool = False,
    ) -> None:
        super().__init__(
            audio_path,
            name=name,
            media_type=media_type,
            cost_usd=cost_usd,
            should_fail=should_fail,
            error_message="music provider unavailable (injected)",
        )


class MockCoverProvider(_LocalAssetProvider):
    """OFFLINE cover-art stand-in (GMI FLUX / DALL·E-shaped)."""

    _stage = "cover"

    def __init__(
        self,
        image_path: Path,
        *,
        name: str = "gmi-flux",
        media_type: str = "image/png",
        cost_usd: float = 0.003,
        should_fail: bool = False,
    ) -> None:
        super().__init__(
            image_path,
            name=name,
            media_type=media_type,
            cost_usd=cost_usd,
            should_fail=should_fail,
            error_message="cover provider unavailable (injected)",
        )
