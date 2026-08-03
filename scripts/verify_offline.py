#!/usr/bin/env python3
"""OFFLINE end-to-end proof — the demo-day disaster fallback, zero network.

Runs against MockProvider-class primitives + LocalDirBackend + stdlib-SQLite:
  1. happy path       -> 3-stage fan-out; episode produced + verifies
  2. chaos failover   -> primary TTS rung down -> ladder rung 2 ships the episode
  3. manifest tamper  -> editing embedded provenance flips verify() to False
  4. parallel fan-out -> narration+music+cover land together; event log ordered;
                         run/stage/event rows persisted (SSE relay source)

Exit 0 iff all invariants hold. P1 slice of the full arsenal (chaos + tamper
matrix expands in P7).

    OFFLINE=1 uv run python scripts/verify_offline.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("OFFLINE", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from castiron.db import Database  # noqa: E402
from castiron.media import extract_manifest, verify_file  # noqa: E402
from castiron.pipeline import STAGE_ORDER, run_offline_episode  # noqa: E402

# em-dash pacing trap (SEED_DATA space_update) — makes the gate genuinely iterate
GATED_SCRIPT = (
    "Tonight on the space update — and this is where naive TTS trips — the rover "
    "crossed the ridge, paused — for a long dramatic beat — then rolled on."
)


def _check(label: str, cond: bool, detail: str = "") -> bool:
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {label}" + (f"  — {detail}" if detail else ""))
    return cond


def scenario_happy(root: Path) -> bool:
    print("\n1) HAPPY PATH (3-stage fan-out)")
    r = run_offline_episode(store_root=root, run_id="happy", db=Database(":memory:"))
    ok = True
    ok &= _check("run completed + manifest verifies", r.manifest_verified,
                 f"hash={r.manifest_hash[:16]}")
    ok &= _check("episode has in-file manifest (inline embed)", r.embed_method == "inline",
                 f"method={r.embed_method}")
    ok &= _check("episode file verifies (genblaze-verify equivalent)", r.episode_verified)
    ok &= _check("all 3 stages succeeded", all(s.state == "succeeded" for s in r.stages),
                 " · ".join(f"{s.name}={s.provider_used}" for s in r.stages))
    ok &= _check("cost summed across stages", r.cost_usd > 0, f"${r.cost_usd:.4f}")
    ok &= _check("no fallback needed on happy path", not r.fallback_used,
                 f"narration={r.model_used}")
    return ok


def scenario_chaos(root: Path) -> bool:
    print("\n2) CHAOS FAILOVER (primary TTS rung down → cross-provider ladder)")
    r = run_offline_episode(store_root=root, run_id="chaos", chaos="tts",
                            db=Database(":memory:"))
    narr = r.stage("narration")
    ok = True
    ok &= _check("ladder fell back to rung 2", r.fallback_used,
                 f"requested={r.model_requested} used={r.model_used}")
    ok &= _check("manifest records the ACTUAL rung (I3)", narr.fallback_rung == 1,
                 f"provider={narr.provider_used} rung={narr.fallback_rung}")
    ok &= _check("episode still produced + verifies", r.ok)
    ok &= _check("music + cover unaffected by narration chaos",
                 r.stage("music").state == "succeeded"
                 and r.stage("cover").state == "succeeded")
    return ok


def scenario_tamper(root: Path) -> bool:
    print("\n3) MANIFEST TAMPER RED-PATH")
    r = run_offline_episode(store_root=root, run_id="tamper", db=Database(":memory:"))
    ep = r.episode_path
    from mutagen.id3 import ID3

    tags = ID3(ep)
    frame = tags.get("TXXX:genblaze:manifest")
    doc = json.loads(frame.text[0])
    doc["run"]["steps"][0]["prompt"] = "TAMPERED PROVENANCE"
    frame.text = [json.dumps(doc)]
    tags.save(ep)

    tampered = extract_manifest(ep)
    ok = True
    ok &= _check("tampered manifest fails verify_hash()", not tampered.verify_hash())
    ok &= _check("tampered file fails verify_file()", not verify_file(ep))
    return ok


def scenario_fanout(root: Path) -> bool:
    print("\n4) PARALLEL FAN-OUT + EVENT LOG (SSE relay source, persisted)")
    db = Database(":memory:")
    r = run_offline_episode(store_root=root, run_id="fan", db=db)
    ok = True
    ok &= _check("stage order narration→music→cover",
                 [s.name for s in r.stages] == list(STAGE_ORDER))
    ok &= _check("3 assets + manifest landed on the sink",
                 sum(k.endswith((".mp3", ".png")) for k in r.object_keys) == 3
                 and any(k.endswith("manifest.json") for k in r.object_keys),
                 f"{len(r.object_keys)} objects")
    events = db.list_events("fan")
    ordered = ([e.type for e in events][0] == "pipeline.started"
               and [e.type for e in events][-1] == "pipeline.completed"
               and [e.id for e in events] == sorted(e.id for e in events))
    ok &= _check("event log ordered + persisted (runs/stages/events)", ordered,
                 f"{len(events)} events · run.state={db.get_run('fan').state}")
    ok &= _check("stage rows carry provider/model/sha256",
                 all(s.sha256 and s.model_used for s in r.stages))
    return ok


def main() -> int:
    print("CastIron OFFLINE verification  (mode=OFFLINE, network=none)")
    with tempfile.TemporaryDirectory(prefix="castiron-verify-") as td:
        root = Path(td)
        results = [
            scenario_happy(root),
            scenario_chaos(root),
            scenario_tamper(root),
            scenario_fanout(root),
        ]
    passed = all(results)
    print("\n" + ("ALL GREEN — 0 dropped episodes" if passed else "FAILURES ABOVE"))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
