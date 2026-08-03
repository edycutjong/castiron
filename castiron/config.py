"""Runtime configuration for CastIron.

Deliberately dependency-light (plain ``os.environ``) so the OFFLINE path has no
import-time surprises. Every key here is mirrored in ``.env.example``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _truthy(val: str | None) -> bool:
    return (val or "").strip().lower() in {"1", "true", "yes", "on"}


def _has_b2_creds() -> bool:
    return bool(os.environ.get("B2_KEY_ID") and os.environ.get("B2_APP_KEY"))


@dataclass(frozen=True)
class Settings:
    """Resolved settings snapshot."""

    offline: bool
    local_store: Path
    media_bucket: str
    published_bucket: str
    max_run_cost_usd: float

    @property
    def mode(self) -> str:
        return "OFFLINE" if self.offline else "LIVE"


def load_settings() -> Settings:
    """Resolve settings from the environment.

    OFFLINE is first-class: it is ON when ``OFFLINE=1`` is set OR when no B2
    credentials are present. This makes the no-credentials dev path and the
    demo-day disaster fallback the same, always-green path.
    """
    forced_offline = _truthy(os.environ.get("OFFLINE"))
    offline = forced_offline or not _has_b2_creds()
    # `or` (not just get's default) so an env key set-but-empty — common in .env
    # files — still resolves to the absolute default. An empty value would yield
    # Path("")==".", a RELATIVE root that breaks the S3 sink's as_uri() upload.
    local_store = Path(
        os.environ.get("CASTIRON_LOCAL_STORE") or REPO_ROOT / "var" / "local-store"
    ).expanduser().resolve()
    return Settings(
        offline=offline,
        local_store=local_store,
        media_bucket=os.environ.get("B2_MEDIA_BUCKET", "ci-media"),
        published_bucket=os.environ.get("B2_PUBLISHED_BUCKET", "ci-published"),
        max_run_cost_usd=float(os.environ.get("MAX_RUN_COST_USD", "1.50")),
    )


settings = load_settings()
