#!/usr/bin/env python3
"""CastIron reproducible benchmark — the numbers, provable on a fresh clone.

One command, zero config, fixed seed, network-free:

    OFFLINE=1 .venv/bin/python bench.py        # or: python bench.py (see README)

It drives the REAL episode engine (``castiron.pipeline.run_offline_episode``) over
the operator-seeded scripts in ``seed/episodes.json`` and measures the one thing
CastIron exists to guarantee: **zero dropped episodes, even when the primary voice
provider dies mid-render.**

Four scenarios, every one a correctness gate (a failure exits non-zero):

  1. HEALTHY   — provider up: episode renders, manifest verifies, no failover.
  2. FAILOVER  — primary TTS killed on EVERY run: the cross-provider ladder steps
                 down a rung (elevenlabs -> lmnt) and STILL ships a verified episode.
  3. TAMPER    — one byte of embedded provenance edited: verify() must flip to False.
  4. BUDGET    — projected spend over the cap: the run must hard-abort (typed
                 BUDGET_ABORT) BEFORE spending, not after.

Latency is end-to-end orchestration + manifest verify + in-file embed, measured
OFFLINE with mock providers — real-vendor synthesis latency is provider-bound and
deliberately EXCLUDED (see "Methodology & limitations" in DEMO.md). The honest
headline is a reliability number, not a speed number.
"""

from __future__ import annotations

import json
import os
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

# OFFLINE is the demo-day disaster path AND the no-credentials path — force it so
# the benchmark is byte-identical on any machine, with or without B2 keys.
os.environ.setdefault("OFFLINE", "1")

SEED = 42
random.seed(SEED)

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from castiron.db import Database  # noqa: E402
from castiron.media import extract_manifest, verify_file  # noqa: E402
from castiron.pipeline import run_offline_episode  # noqa: E402

WARMUP = 2          # discarded — excludes cold-start (imports, ffmpeg spin-up)
REPEATS = 8         # timed trials per (episode, scenario)


def _percentile(xs: list[float], q: float) -> float:
    """Linear-interpolated percentile (q in [0,1]); xs need not be sorted."""
    if not xs:
        return float("nan")
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(pos)
    frac = pos - lo
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * frac


def _load_seed() -> dict:
    with open(ROOT / "seed" / "episodes.json") as fh:
        return json.load(fh)


def _run(root: Path, ep: dict, run_id: str, chaos: str | None = None):
    return run_offline_episode(
        store_root=root,
        run_id=run_id,
        script=ep["script"],
        chaos=chaos,
        db=Database(":memory:"),
    )


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #
def bench_render(root: Path, episodes: list[dict], chaos: str | None, tag: str):
    """Time REPEATS renders of each seed episode; assert every one ships verified.

    Returns (latencies_ms, shipped, attempted, failures[]).
    """
    latencies: list[float] = []
    shipped = attempted = 0
    failures: list[str] = []

    # Warm-up (discarded): first ffmpeg/import cost must not pollute the tail.
    for i in range(WARMUP):
        _run(root, episodes[i % len(episodes)], f"{tag}-warm-{i}", chaos)

    for ep in episodes:
        for r in range(REPEATS):
            attempted += 1
            rid = f"{tag}-{ep['id']}-{r}"
            t0 = time.perf_counter()
            res = _run(root, ep, rid, chaos)
            latencies.append((time.perf_counter() - t0) * 1000.0)

            ok = res.ok and res.episode_verified and res.manifest_verified
            if chaos == "tts":
                # Must have actually failed over to a lower rung AND still shipped.
                narr = res.stage("narration")
                ok = ok and narr is not None and narr.fallback_rung == 1
            if ok:
                shipped += 1
            else:
                failures.append(f"{tag}/{ep['id']}#{r}: ok={res.ok} "
                                f"verified={res.episode_verified} "
                                f"rung={getattr(res.stage('narration'),'fallback_rung',None)}")
    return latencies, shipped, attempted, failures


def bench_tamper(root: Path, hero: dict) -> tuple[bool, str]:
    """Edit one byte of embedded provenance; verify() must flip to False."""
    from mutagen.id3 import ID3

    res = _run(root, hero, "tamper-hero")
    if not res.episode_verified:
        return False, "pre-tamper episode did not verify"
    ep_path = res.episode_path
    tags = ID3(ep_path)
    frame = tags.get("TXXX:genblaze:manifest")
    doc = json.loads(frame.text[0])
    doc["run"]["steps"][0]["prompt"] = "TAMPERED PROVENANCE"
    frame.text = [json.dumps(doc)]
    tags.save(ep_path)

    tampered = extract_manifest(ep_path)
    caught = (not tampered.verify_hash()) and (not verify_file(ep_path))
    return caught, ("tamper detected" if caught else "TAMPER NOT DETECTED")


def bench_budget(root: Path, hero: dict) -> tuple[bool, str]:
    """chaos=budget must trip the pre-spend projection and hard-abort."""
    res = _run(root, hero, "budget-hero", chaos="budget")
    aborted = res.budget_aborted and res.state == "failed" and not res.episode_verified
    return aborted, ("BUDGET_ABORT before spend" if aborted else "budget cap NOT enforced")


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def _lat_row(name: str, xs: list[float]) -> str:
    return (f"  {name:<22} n={len(xs):<3} "
            f"p50={_percentile(xs,0.50):6.1f}ms  "
            f"p95={_percentile(xs,0.95):6.1f}ms  "
            f"mean={statistics.mean(xs):6.1f}ms")


def main() -> int:
    data = _load_seed()
    episodes = data["episodes"]
    hero = next(e for e in episodes if e.get("hero")) if any(
        e.get("hero") for e in episodes) else episodes[0]

    print("CastIron benchmark  (mode=OFFLINE, network=none, "
          f"seed={SEED}, repeats={REPEATS}, warmup={WARMUP})")
    print(f"seed dataset: {len(episodes)} episodes · hero='{hero['id']}'\n")

    with tempfile.TemporaryDirectory(prefix="castiron-bench-") as td:
        root = Path(td)

        healthy_lat, h_ship, h_att, h_fail = bench_render(root, episodes, None, "healthy")
        failover_lat, f_ship, f_att, f_fail = bench_render(root, episodes, "tts", "failover")
        tamper_ok, tamper_msg = bench_tamper(root, hero)
        budget_ok, budget_msg = bench_budget(root, hero)

    total_ship = h_ship + f_ship
    total_att = h_att + f_att
    dropped = total_att - total_ship

    print("Latency  (end-to-end render + manifest verify + in-file embed)")
    print(_lat_row("healthy", healthy_lat))
    print(_lat_row("failover (rung down)", failover_lat))

    print("\nCorrectness gates")
    checks = [
        ("healthy: every episode ships verified", not h_fail, f"{h_ship}/{h_att}"),
        ("failover: rung steps down + still ships", not f_fail, f"{f_ship}/{f_att}"),
        ("tamper: verify() flips to False", tamper_ok, tamper_msg),
        ("budget: hard-abort before spend", budget_ok, budget_msg),
    ]
    for label, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label:<44} {detail}")
    for f in (h_fail + f_fail):
        print(f"    ! {f}")

    print("\n" + "=" * 66)
    print(f"HEADLINE: {total_ship}/{total_att} episodes shipped hash-verified "
          f"across healthy + forced-outage runs — {dropped} dropped.")
    print(f"          failover p50={_percentile(failover_lat,0.50):.0f}ms · "
          f"p95={_percentile(failover_lat,0.95):.0f}ms "
          f"(OFFLINE orchestration; vendor synth excluded).")
    print("=" * 66)

    all_ok = not h_fail and not f_fail and tamper_ok and budget_ok and dropped == 0
    print("\n" + ("ALL GREEN — 0 dropped episodes" if all_ok
                  else "FAILURES ABOVE — see gates"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
