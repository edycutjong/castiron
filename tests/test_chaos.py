"""Chaos switch (E12) — the parseable demo control surface CHAOS_FAIL.

``CHAOS_FAIL=<provider>[:stage][:timing]`` drives fault injection identically from
the console, the API, verify_offline and the chaos matrix.
"""

from __future__ import annotations

import pytest

from castiron.chaos import (
    ChaosSpec,
    narration_rung_down,
    parse_chaos,
    resolve_chaos,
)
from castiron.db import Database
from castiron.pipeline import run_episode, run_offline_episode


class _CaptureHub:
    """Records what the runner pushes onto the live SSE rail."""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []
        self.done: list[str] = []

    def publish(self, run_id: str, event: dict) -> None:
        self.published.append((run_id, event))

    def mark_done(self, run_id: str) -> None:
        self.done.append(run_id)


@pytest.mark.parametrize(
    "raw,provider,stage,timing",
    [
        ("elevenlabs", "elevenlabs", "narration", "immediate"),
        ("tts", "tts", "narration", "immediate"),
        ("lmnt", "lmnt", "narration", "immediate"),
        ("stability", "stability", "music", "immediate"),
        ("gmi", "gmi", "cover", "immediate"),
        ("narration:transient", None, "narration", "transient"),
        ("elevenlabs:narration:transient", "elevenlabs", "narration", "transient"),
        ("elevenlabs:transient", "elevenlabs", "narration", "transient"),
        ("elevenlabs:narration:mid-stream", "elevenlabs", "narration", "mid-stream"),
        ("budget", "budget", None, "immediate"),
    ],
)
def test_parse_chaos_forms(raw, provider, stage, timing):
    spec = parse_chaos(raw)
    assert (spec.provider, spec.stage, spec.timing) == (provider, stage, timing)


@pytest.mark.parametrize("raw", ["", None, "none", "off", "garbage-token"])
def test_parse_chaos_inert(raw):
    spec = parse_chaos(raw)
    assert spec.active is False


def test_narration_rung_down_truth_table():
    # provider tokens force rungs 0..depth down; transient never forces down
    assert [narration_rung_down(parse_chaos("tts"), i) for i in range(3)] == [True, False, False]
    assert [narration_rung_down(parse_chaos("lmnt"), i) for i in range(3)] == [True, True, False]
    assert [narration_rung_down(parse_chaos("hume"), i) for i in range(3)] == [True, True, True]
    # generic narration fault collapses the whole ladder
    assert [narration_rung_down(parse_chaos("narration"), i) for i in range(3)] == [True, True, True]
    # a transient fault resumes, never forces a rung down
    assert [narration_rung_down(parse_chaos("narration:transient"), i) for i in range(3)] == [False, False, False]
    # a music fault leaves narration alone
    assert [narration_rung_down(parse_chaos("stability"), i) for i in range(3)] == [False, False, False]


def test_resolve_chaos_precedence(monkeypatch):
    # explicit spec wins
    spec = ChaosSpec(provider="lmnt", stage="narration", timing="immediate")
    assert resolve_chaos(spec) is spec
    # explicit "" forces no-chaos regardless of env (hermetic tests)
    monkeypatch.setenv("CHAOS_FAIL", "hume")
    assert resolve_chaos("").active is False
    # None falls back to the env toggle
    assert resolve_chaos(None).provider == "hume"


def test_budget_chaos_aborts_typed(store):
    r = run_offline_episode(chaos="budget", store_root=store, run_id="bud",
                            db=(db := Database(":memory:")))
    assert r.state == "failed"
    assert r.budget_aborted is True
    assert "BUDGET_ABORT" in (db.get_run("bud").error or "")
    assert any(e.type == "budget.abort" for e in db.list_events("bud"))


def test_narration_rung_down_unknown_narration_provider():
    """A spec that targets the narration stage but whose provider has no ladder
    depth (e.g. a mislabelled music provider) forces no rung down — defensive."""
    spec = ChaosSpec(provider="stability", stage="narration", timing="immediate")
    assert narration_rung_down(spec, 0) is False
    assert narration_rung_down(spec, 2) is False


def test_chaos_to_token_variants():
    assert parse_chaos("budget").to_token() == "budget:immediate"
    assert parse_chaos("narration:transient").to_token() == "narration:transient"
    assert parse_chaos("elevenlabs:transient").to_token() == "elevenlabs:narration:transient"
    assert ChaosSpec().to_token() == "none"


def test_music_chaos_degrades_honestly(store):
    """Music has no fallback ladder, so a music fault fail-fasts the run into a
    typed DEGRADED state — recorded, never silently dropped."""
    r = run_offline_episode(chaos="music", store_root=store, run_id="mus",
                            db=Database(":memory:"))
    assert r.ok is False
    assert r.state == "failed"
    assert r.stage("music").state == "failed"   # the fault is recorded, not hidden


async def test_budget_abort_pushes_to_live_rail_and_closes_stream(store):
    """The pre-spend BUDGET_ABORT must reach the live SSE rail AND close the
    stream (mark_done) so a watching client sees the typed abort, not a hang."""
    hub = _CaptureHub()
    db = Database(":memory:")
    r = await run_episode(chaos="budget", store_root=store, run_id="budsse",
                          db=db, hub=hub, publish=True)
    assert r.budget_aborted is True
    assert r.state == "failed"
    # abort event pushed live with the typed reason
    assert any(ev.get("reason") == "BUDGET_ABORT" for _, ev in hub.published)
    # every stage marked aborted (no spend happened)
    assert all(s.state == "aborted" for s in db.list_stages("budsse"))
    # the live stream was explicitly closed for the watcher
    assert hub.done == ["budsse"]
