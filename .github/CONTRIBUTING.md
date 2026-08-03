# Contributing

Thanks for your interest in improving CastIron! 🎉

## Getting Started
1. Fork the repo and branch from `main`: `git checkout -b feat/your-feature`
2. Install [`uv`](https://docs.astral.sh/uv/) and sync deps: `uv sync --extra dev`
3. Install `ffmpeg` (audio fixtures + mixing): `brew install ffmpeg` / `apt-get install -y ffmpeg`
4. Run the always-green offline path: `OFFLINE=1 .venv/bin/python scripts/verify_offline.py`

> Run Python via `.venv/bin/python` (not `uv run`) in an offline shell — `uv run`
> re-syncs and can drop the pre-installed `genblaze` wheels when the network is absent.

## Before You Open a PR
- Lint passes: `ruff check .`
- Tests pass: `OFFLINE=1 .venv/bin/python -m pytest`
- Offline end-to-end smoke passes: `OFFLINE=1 .venv/bin/python scripts/verify_offline.py` → "ALL GREEN — 0 dropped episodes"
- Benchmark still green (if you touched the engine): `OFFLINE=1 .venv/bin/python bench.py`
- Add or update tests for any behavior change.
- Keep commits conventional (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).

## The OFFLINE contract
`OFFLINE=1` (mock providers + `LocalDirBackend`, zero network, zero credentials) must
stay green at all times — it is both the no-credentials dev path and the demo-day
disaster fallback. Never merge a change that reds the offline suite.

## Reporting Bugs / Requesting Features
Open an issue using the provided templates. Include repro steps, expected vs.
actual behavior, and environment details.
