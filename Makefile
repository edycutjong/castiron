# CastIron — developer harness. OFFLINE is the always-green, zero-credential path.
PY := .venv/bin/python

.PHONY: help sync lint test offline e2e bench security-scan ci

help:
	@echo "CastIron make targets:"
	@echo "  make sync           # uv sync --extra dev"
	@echo "  make lint           # ruff check ."
	@echo "  make test           # pytest (OFFLINE)"
	@echo "  make offline        # end-to-end offline smoke (4 scenarios)"
	@echo "  make e2e            # boot the API + healthz + offline end-to-end"
	@echo "  make bench          # reproducible benchmark (p50/p95, 0 dropped)"
	@echo "  make security-scan  # pip-audit dependency scan"
	@echo "  make ci             # lint + test + offline (the CI hard gate, locally)"

sync:
	uv sync --extra dev

lint:
	ruff check .

test:
	OFFLINE=1 $(PY) -m pytest

offline:
	OFFLINE=1 $(PY) scripts/verify_offline.py

e2e:
	@echo "🎭 API E2E: boot uvicorn, probe /healthz, run offline end-to-end..."
	OFFLINE=1 $(PY) -m uvicorn app.main:app --port 8000 & \
	  SERVER_PID=$$!; sleep 3; \
	  curl -fsS http://127.0.0.1:8000/healthz && echo " ✅ healthz"; \
	  kill $$SERVER_PID
	OFFLINE=1 $(PY) scripts/verify_offline.py

bench:
	OFFLINE=1 $(PY) bench.py

security-scan:
	@echo "=== PIP AUDIT ==="
	$(PY) -m pip install --quiet pip-audit && $(PY) -m pip_audit || true

ci: lint test offline
	@echo "✅ Local CI hard gate green"
