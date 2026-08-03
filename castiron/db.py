"""Run metadata store — the ``runs`` / ``stages`` / ``events`` tables.

ARCHITECTURE.md specifies **SQLite (SQLModel)**. In this build sandbox the network
is disabled and the ``sqlmodel`` wheel is not fetchable/cached, so the store is
implemented on the Python **stdlib ``sqlite3``** with the *identical* schema,
wrapped in a thin repository (``Database``) with row dataclasses. This keeps the
always-green OFFLINE path dependency-free; swapping in SQLModel later is a
mechanical change behind this same surface. (See DEVIATIONS.md.)

Schema (verbatim from ARCHITECTURE.md "DB schema"):

    runs(id, created_at, state, script_sha, voice, music_style, chaos_flag,
         episode_key, published_key, manifest_hash, error)
    stages(run_id, name, state, provider_used, model_used, attempt, fallback_rung,
           b2_key, sha256, started_at, finished_at)
    events(id, run_id, source{pipeline|b2|gate}, type, payload_json, at)
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from castiron.config import settings


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class RunRow:
    id: str
    created_at: str
    state: str
    script_sha: str | None = None
    voice: str | None = None
    music_style: str | None = None
    chaos_flag: str | None = None
    episode_key: str | None = None
    published_key: str | None = None
    manifest_hash: str | None = None
    error: str | None = None


@dataclass
class StageRow:
    run_id: str
    name: str
    state: str
    provider_used: str | None = None
    model_used: str | None = None
    attempt: int = 0
    fallback_rung: int | None = None
    b2_key: str | None = None
    sha256: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


@dataclass
class EventRow:
    id: int
    run_id: str
    source: str
    type: str
    payload_json: str
    at: str


_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    state         TEXT NOT NULL,
    script_sha    TEXT,
    voice         TEXT,
    music_style   TEXT,
    chaos_flag    TEXT,
    episode_key   TEXT,
    published_key TEXT,
    manifest_hash TEXT,
    error         TEXT
);
CREATE TABLE IF NOT EXISTS stages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL REFERENCES runs(id),
    name          TEXT NOT NULL,
    state         TEXT NOT NULL,
    provider_used TEXT,
    model_used    TEXT,
    attempt       INTEGER NOT NULL DEFAULT 0,
    fallback_rung INTEGER,
    b2_key        TEXT,
    sha256        TEXT,
    started_at    TEXT,
    finished_at   TEXT,
    UNIQUE(run_id, name)
);
CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL REFERENCES runs(id),
    source       TEXT NOT NULL,
    type         TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    at           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_events_run ON events(run_id, id);
CREATE INDEX IF NOT EXISTS ix_stages_run ON stages(run_id);
"""


class Database:
    """Thread-safe SQLite repository for run/stage/event state.

    One connection is shared across the FastAPI request handlers and the
    background run task; writes are serialized with a lock and WAL is enabled so
    concurrent readers never block.
    """

    def __init__(self, url: str | Path = ":memory:") -> None:
        self.url = str(url)
        is_file = self.url not in (":memory:", "") and not self.url.startswith("file::memory:")
        if is_file:
            Path(self.url).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            self.url, check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        if is_file:
            self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self.init()

    def init(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- runs ------------------------------------------------------------------

    def insert_run(
        self,
        run_id: str,
        *,
        state: str = "queued",
        script_sha: str | None = None,
        voice: str | None = None,
        music_style: str | None = None,
        chaos_flag: str | None = None,
    ) -> RunRow:
        row = RunRow(
            id=run_id,
            created_at=_now(),
            state=state,
            script_sha=script_sha,
            voice=voice,
            music_style=music_style,
            chaos_flag=chaos_flag,
        )
        with self._lock:
            self._conn.execute(
                "INSERT INTO runs(id, created_at, state, script_sha, voice, "
                "music_style, chaos_flag) VALUES(?,?,?,?,?,?,?)",
                (row.id, row.created_at, row.state, row.script_sha, row.voice,
                 row.music_style, row.chaos_flag),
            )
        return row

    def update_run(self, run_id: str, **fields: Any) -> None:
        allowed = {"state", "episode_key", "published_key", "manifest_hash", "error"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return
        cols = ", ".join(f"{k}=?" for k in sets)
        with self._lock:
            self._conn.execute(
                f"UPDATE runs SET {cols} WHERE id=?", (*sets.values(), run_id)
            )

    def get_run(self, run_id: str) -> RunRow | None:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM runs WHERE id=?", (run_id,))
            r = cur.fetchone()
        return RunRow(**dict(r)) if r else None

    def list_runs(self, limit: int = 50) -> list[RunRow]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            )
            rows = cur.fetchall()
        return [RunRow(**dict(r)) for r in rows]

    # -- stages ----------------------------------------------------------------

    def upsert_stage(self, run_id: str, name: str, **fields: Any) -> None:
        """Insert the stage if new, else patch the supplied columns."""
        allowed = {"state", "provider_used", "model_used", "attempt",
                   "fallback_rung", "b2_key", "sha256", "started_at", "finished_at"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        with self._lock:
            cur = self._conn.execute(
                "SELECT id FROM stages WHERE run_id=? AND name=?", (run_id, name)
            )
            exists = cur.fetchone() is not None
            if not exists:
                self._conn.execute(
                    "INSERT INTO stages(run_id, name, state) VALUES(?,?,?)",
                    (run_id, name, sets.pop("state", "pending")),
                )
            if sets:
                cols = ", ".join(f"{k}=?" for k in sets)
                self._conn.execute(
                    f"UPDATE stages SET {cols} WHERE run_id=? AND name=?",
                    (*sets.values(), run_id, name),
                )

    def list_stages(self, run_id: str) -> list[StageRow]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT run_id, name, state, provider_used, model_used, attempt, "
                "fallback_rung, b2_key, sha256, started_at, finished_at "
                "FROM stages WHERE run_id=? ORDER BY id", (run_id,)
            )
            rows = cur.fetchall()
        return [StageRow(**dict(r)) for r in rows]

    # -- events ----------------------------------------------------------------

    def insert_event(
        self, run_id: str, source: str, type: str, payload_json: str,
        at: str | None = None,
    ) -> int:
        at = at or _now()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO events(run_id, source, type, payload_json, at) "
                "VALUES(?,?,?,?,?)", (run_id, source, type, payload_json, at)
            )
            return int(cur.lastrowid)

    def list_events(self, run_id: str, after_id: int = 0) -> list[EventRow]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT id, run_id, source, type, payload_json, at FROM events "
                "WHERE run_id=? AND id>? ORDER BY id", (run_id, after_id)
            )
            rows = cur.fetchall()
        return [EventRow(**dict(r)) for r in rows]


# -- process-wide default instance --------------------------------------------

_DEFAULT: Database | None = None
_DEFAULT_LOCK = threading.Lock()


def default_db_url() -> str:
    import os
    env = os.environ.get("CASTIRON_DB_URL")
    if env:
        return env
    return str(settings.local_store / "castiron.db")


def get_db() -> Database:
    """Return the process-wide default Database (created on first use)."""
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = Database(default_db_url())
        return _DEFAULT


def set_db(db: Database) -> None:
    """Override the process-wide default (tests / app startup)."""
    global _DEFAULT
    with _DEFAULT_LOCK:
        _DEFAULT = db
