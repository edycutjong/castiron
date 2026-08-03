"""Shared test fixtures. OFFLINE is forced before any castiron import."""

from __future__ import annotations

import os

os.environ["OFFLINE"] = "1"
os.environ.pop("B2_KEY_ID", None)
os.environ.pop("B2_APP_KEY", None)

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_db():
    """Keep the process-wide default DB hermetic: reset to a fresh in-memory
    instance after every test so no test observes another's rows or a closed
    connection."""
    yield
    from castiron.db import Database, set_db

    set_db(Database(":memory:"))


@pytest.fixture
def store(tmp_path: Path) -> Path:
    """A fresh on-disk object store root."""
    return tmp_path / "store"


@pytest.fixture
def tmp_db(tmp_path: Path):
    """A fresh file-backed Database, also bound as the process default."""
    from castiron.db import Database, set_db

    db = Database(tmp_path / "castiron.db")
    set_db(db)
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    """FastAPI TestClient (imported lazily so OFFLINE env is already set)."""
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)
