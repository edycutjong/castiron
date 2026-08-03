# Feature request: cross-provider fallback (a provider ladder), not just `fallback_models`

**Component:** `genblaze-core` · `Pipeline.step(...)` failover
**Type:** feature request / API gap
**Severity:** medium (resilience is the headline use-case for generative pipelines)
**Env:** `genblaze==0.4.1` (genblaze-core 0.3.4, genblaze-s3 0.3.4), Python 3.11, macOS; installed via `uv`. Surface confirmed with `inspect.signature(Pipeline.step)`.

## Summary

`.step(..., fallback_models=[...])` fails over **within a single provider** — it retries
alternate *model strings* against the *same* provider instance. There is no first-class way
to fail over to a **different provider** (different SDK, auth, endpoint, infra). For a TTS/image
pipeline, provider-level independence is the whole point of a fallback ladder: an ElevenLabs
outage should step down to LMNT, then Hume — three different vendors, three uncorrelated
failure domains. Today that requires hand-rolling the loop outside genblaze.

## Minimal repro

```python
from genblaze_core import Pipeline, Modality
# elevenlabs, lmnt, hume are three DIFFERENT provider classes with different auth.
from genblaze_elevenlabs import ElevenLabsTTSProvider   # rung 1
from genblaze_lmnt import LMNTProvider                   # rung 2
from genblaze_hume import HumeTTSProvider                # rung 3

# What you can express today — same provider, alternate MODELS only:
Pipeline("tts").step(
    ElevenLabsTTSProvider(),
    model="eleven_multilingual_v2",
    fallback_models=["eleven_turbo_v2"],   # still ElevenLabs; an EL outage kills all rungs
    prompt=script, modality=Modality.AUDIO,
).run(raise_on_failure=True)

# What there is NO parameter for — fall over to a DIFFERENT provider:
#   fallback_providers=[LMNTProvider(model="blizzard"), HumeTTSProvider(model="octave")]
# `.step()` accepts exactly one `provider=`; `fallback_models` is `list[str]`.
```

`inspect.signature(Pipeline.step)` →
`step(self, provider, *, model, ..., fallback_models: list[str] | None = None, ...)` —
one provider, model-strings only.

## Observed vs expected

- **Observed:** cross-provider failover is impossible through the documented surface. If the
  primary provider (not just a model) is down/misconfigured/rate-limited at the account level,
  every `fallback_models` entry fails too, and the step drops.
- **Expected:** a way to declare an ordered list of *provider rungs*, each with its own model
  and (ideally) retry policy, that are tried in sequence; the manifest records which rung
  actually ran.

## Impact

We are building a "self-healing" episode factory whose headline feature is exactly this ladder.
We had to implement our own composite provider (`LadderTTSProvider(SyncProvider)`) that loops
over distinct sub-providers and records the winning rung into `step.metadata` + `step.model`.
It works and the manifest correctly reflects the actual rung — but this is core resilience
plumbing that most users will re-implement (and get subtly wrong: partial-output reset on a
failed rung, per-rung error typing, provenance of the rung that ran).

## Proposed API

```python
from genblaze_core import Ladder, Rung, RetryPolicy, Modality

ladder = Ladder(
    Rung(ElevenLabsTTSProvider(), model="eleven_multilingual_v2",
         retry=RetryPolicy.conservative()),
    Rung(LMNTProvider(), model="blizzard"),
    Rung(HumeTTSProvider(), model="octave"),
    on_fallback=notify,           # callback(rung_index, rung, error)
)

# either as a step-level construct...
Pipeline("tts").step(ladder, prompt=script, modality=Modality.AUDIO).run()
# ...or standalone, returning the winning rung index + step result:
outcome = ladder.run(prompt=script, modality=Modality.AUDIO)
assert outcome.rung_index in (0, 1, 2)
```

Minimum viable alternative if a new class is too much: let `.step()` accept
`fallback_providers: list[tuple[BaseProvider, str]]` (provider, model) tried after the primary,
and record the executed provider/model on the step (as `fallback_models` already records the
model). The manifest **must** show the rung that ran so a fallback is never hidden.

## Notes

We're happy to contribute the extraction — our `LadderTTSProvider` is ~70 LOC and already
passes provider-independent chaos tests (rung-1-down → rung-2 records; total-collapse fails
honestly). This is planned as a small `genblaze-ladder` pip package; upstreaming it would be
better for everyone.
