"""Media helpers: OFFLINE audio fixtures + in-file manifest embed/verify.

Wraps the genblaze media surface we verified at build:
- ``SmartEmbedder().embed(source, manifest, output)`` writes an in-file manifest
  (ID3 TXXX for MP3 via mutagen; RIFF for WAV). Returns an ``EmbedResult`` whose
  ``method`` is ``"inline"`` on success or ``"sidecar"`` on degraded fallback.
- ``get_handler(mime).verify(path)`` == extract + ``Manifest.verify()`` — the
  Python equivalent of the (unshipped) ``genblaze verify`` CLI.

Verification boundary (verified at build, see docs/friction-log.md): the SDK's
``Manifest.verify()`` checks the canonical_hash over the run record + that each
output declares a sha256. It does **not** re-hash the audio payload, so it
catches manifest/provenance tampering but not an audio re-encode. CastIron's
episode-level authenticity check (payload re-hash) lands in P4.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

from genblaze_core.media import SmartEmbedder, get_handler, guess_mime
from genblaze_core.models.asset import Asset
from genblaze_core.models.manifest import Manifest


class FfmpegMissingError(RuntimeError):
    """Raised when ffmpeg is not on PATH (needed for fixtures + real mixing)."""


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def synth_tone(
    path: Path,
    *,
    seconds: float = 1.5,
    freq: int = 330,
    mp3: bool = True,
) -> Path:
    """Synthesize a deterministic sine-tone audio fixture with ffmpeg.

    Used as the OFFLINE stand-in for TTS narration so the manifest/embed/verify
    chain exercises real audio bytes with zero network and zero credentials.
    """
    if not ffmpeg_available():
        raise FfmpegMissingError("ffmpeg not found on PATH")
    path.parent.mkdir(parents=True, exist_ok=True)
    codec = ["-c:a", "libmp3lame", "-b:a", "128k"] if mp3 else []
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}",
            "-ac", "1", "-ar", "44100", *codec, str(path),
        ],
        check=True,
    )
    return path


def synth_png(
    path: Path,
    *,
    size: str = "512x512",
    color: str = "0x1a1a1a",
    label: str | None = None,
) -> Path:
    """Synthesize a deterministic PNG fixture with ffmpeg (OFFLINE cover art).

    Stand-in for a GMI FLUX / DALL·E cover so the IMAGE stage lands real PNG
    bytes (with a real sha256) through the manifest/sink chain, zero network.
    """
    if not ffmpeg_available():
        raise FfmpegMissingError("ffmpeg not found on PATH")
    path.parent.mkdir(parents=True, exist_ok=True)
    vf = []
    if label:
        # drawtext is best-effort (font availability varies); ignore if it fails.
        vf = ["-vf", f"drawtext=text='{label}':fontcolor=white:fontsize=28:x=20:y=20"]
    try:
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"color=c={color}:s={size}",
                *vf, "-frames:v", "1", str(path),
            ],
            check=True,
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"color=c={color}:s={size}",
                "-frames:v", "1", str(path),
            ],
            check=True,
        )
    return path


def local_asset(path: Path, *, media_type: str | None = None) -> Asset:
    """Build a genblaze Asset for a local file (file:// URL + real sha256)."""
    raw = path.read_bytes()
    return Asset(
        url=path.as_uri(),
        media_type=media_type or guess_mime(path),
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
    )


def embed_manifest(audio_path: Path, manifest: Manifest, output: Path):
    """Embed ``manifest`` into ``audio_path`` (or ``output``); return EmbedResult."""
    output.parent.mkdir(parents=True, exist_ok=True)
    return SmartEmbedder().embed(audio_path, manifest, output=output)


def verify_file(path: Path) -> bool:
    """Verify an asset's embedded manifest (genblaze-verify equivalent)."""
    handler = get_handler(guess_mime(path))
    if handler is None:
        raise ValueError(f"no media handler for {path} ({guess_mime(path)})")
    return handler.verify(path)


def extract_manifest(path: Path) -> Manifest:
    """Extract the embedded manifest from a media file."""
    handler = get_handler(guess_mime(path))
    if handler is None:
        raise ValueError(f"no media handler for {path} ({guess_mime(path)})")
    return handler.extract(path)
