"""live_smoke.py stays CI-safe: with no B2 creds it must report NOT CONFIGURED
(exit 2), never crash or falsely pass."""

from __future__ import annotations

import subprocess
import sys


def test_live_smoke_not_configured_without_creds(monkeypatch):
    monkeypatch.delenv("B2_KEY_ID", raising=False)
    monkeypatch.delenv("B2_APP_KEY", raising=False)
    proc = subprocess.run(
        [sys.executable, "scripts/live_smoke.py"],
        capture_output=True, text=True,
        env={"OFFLINE": "1", "PATH": __import__("os").environ.get("PATH", "")},
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "NOT CONFIGURED" in proc.stdout
    assert "b2_setup.sh --plan" in proc.stdout
