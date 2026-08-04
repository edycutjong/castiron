"""CastIron — script to published episode, even when your TTS provider dies."""

from __future__ import annotations

__version__ = "1.7.0"

from castiron.backends import LocalDirBackend
from castiron.config import settings
from castiron.pipeline import EpisodeResult, run_offline_episode
from castiron.providers import LocalTTSProvider, failing_provider

__all__ = [
    "__version__",
    "settings",
    "LocalDirBackend",
    "LocalTTSProvider",
    "failing_provider",
    "run_offline_episode",
    "EpisodeResult",
]
