# P2 Resilience Evidence Pack — CastIron

> Phase P2 (Resilience & gate). Purpose: prove the resilience acceptance criteria are met. Everything below is reproducible OFFLINE (no credentials, no network) — the honest substitution status is stated per item.
> Captured 2026-07-05. Test suite: **89 passed, 0 failed, ruff clean**.
> Reproduce all: `OFFLINE=1 uv run python scripts/verify_offline.py` · `uv run pytest`.

## Acceptance criteria
> chaos toggle → rung 2 completes episode; gate iterates on seeded flaw; transient-injection resumes without a double charge.

| # | Criterion | Verdict | Evidence artifact |
|---|---|---|---|
| a | chaos toggle → rung 2 completes episode | ✅ **MET** | `verify_offline.txt` §2 |
| b | gate iterates on seeded flaw | ✅ **MET** | `gate-resume-retry-tests.txt` (test_gate) + below |
| c | transient-injection resumes without double charge | ✅ **MET** | `gate-resume-retry-tests.txt` (test_resume) + below |

## (a) Chaos → cross-provider failover completes the episode
From `verify_offline.txt` §2 "CHAOS FAILOVER":
```
[PASS] ladder fell back to rung 2 — requested=elevenlabs-multilingual-v2 used=lmnt-blizzard
[PASS] manifest records the ACTUAL rung (I3) — provider=lmnt rung=1
[PASS] episode still produced + verifies
[PASS] music + cover unaffected by narration chaos
```
Mechanism: `castiron/ladder.py::LadderTTSProvider` — our OWN try/rung loop over three *distinct* providers (NOT genblaze `fallback_models`, which is in-provider only). The chaos switch (`castiron/chaos.py`, env `CHAOS_FAIL=<provider>[:stage][:timing]`) drives it; the console shows the narration row stepping down live. **Status: OFFLINE (mock providers shaped like the real ones); LIVE parity is P3 with real keys.**

## (b) AgentLoop quality gate iterates on the seeded flaw
`castiron/gate.py` wraps narration in a genblaze `AgentLoop` with **both** documented evaluator types combined in a `CompositeGate`:
- `CallableEvaluator` — loudness (LUFS band) + silence-ratio
- `ThresholdEvaluator` — duration-drift vs script-estimated WPM
Seeded flaw = an em-dash-cluster script that trips pacing on iteration 1; feedback threads into iteration 2 via `AgentContext.last_evaluation.feedback`. Proven by `test_gate.py::test_gate_iterates_once_then_passes`:
```
iterations == 2 · refinements == 1 · iterated is True
[it.passed for records] == [False, True]      # fails once, then passes
started[1].feedback_in contains "pacing"       # feedback actually threaded in
```
Plus `test_gate_uses_both_evaluator_types` (asserts CallableEvaluator AND ThresholdEvaluator present) and `test_gate_does_not_iterate_on_clean_script` (no wasted iteration on good input). **Status: OFFLINE synthetic scorer over mock-audio metadata — deterministic by design; LIVE swaps in real ffmpeg loudnorm/silencedetect at P3–P7.**

## (c) Transient resume — single charge (invariant I5)
`castiron/resume.py::ResumableTTSProvider` + `resume_after_transient_sync()`: a transient mid-generation failure is **resumed** via genblaze `Pipeline.resume_step`/`aresume_step` (SDKCHK #3), not resubmitted. Cost asserted by summing `step.cost_usd` (there is **no `CostLedger` class** — deviation F-03). Proven:
```
test_resume_step_single_charge:  submit_count == 1 · resume_count == 1 · charged_once is True
test_resubmit_would_double_charge_contrast:  resubmit path == 2 × charge   (the anti-pattern, for contrast)
test_integrated_transient_narration_resumes_single_charge:
   resumed is True · fallback_rung == 0 (SAME rung resumed, not fell back) · cost_usd == 0.009
```
Per-rung `RetryPolicy` is now wired in the ladder (`Rung.retry` — conservative for expensive TTS, aggressive for cheap, disabled in tests): `test_retry.py` (5 tests). **Status: OFFLINE; single-charge semantics are SDK-level and carry to LIVE.**

## Honest gaps (do not overclaim)
- All evidence is OFFLINE. "Real B2 bucket", live provider audio, and real ffmpeg loudness are credential/network-gated → P3+ with keys. `scripts/b2_setup.sh --plan` prints the exact real-mode commands.
- Build sandbox has no network → `sqlmodel`→stdlib `sqlite3` and Next.js→static `web/console.html` substitutions stand (DEVIATIONS #1–#2); they port to the real libs in a networked session.
- The gate's OFFLINE scorer is synthetic (deterministic) — it proves the *loop wiring and feedback threading*, not real audio quality. That's the correct thing to prove at P2.

## Verdict
All three criteria MET in reproducible OFFLINE terms, 89 tests green. The differentiator — surviving a provider outage — is demonstrable today. The remaining risk is credential-gated LIVE parity (real B2 Event Notifications driving the stage machine), which the live evidence pack (`../p3-live/`) addresses.
