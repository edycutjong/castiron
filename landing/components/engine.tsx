import { Database, Lock, Radio } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Reveal } from "@/components/reveal";

const GENBLAZE_SURFACES = [
  { api: "Pipeline.astream(max_concurrency=3)", file: "pipeline.py" },
  { api: "ObjectStorageSink · HIERARCHICAL", file: "pipeline.py" },
  { api: "read_manifest(verify=True)", file: "pipeline.py" },
  { api: "SmartEmbedder — in-file ID3 manifest", file: "media.py" },
  { api: "Pipeline.resume_step / aresume_step", file: "resume.py" },
  { api: "AgentLoop · CallableEvaluator + ThresholdEvaluator", file: "gate.py" },
  { api: "ObjectLockConfig(mode=GOVERNANCE)", file: "publish.py" },
  { api: "StorageBackend subclass + ProviderComplianceTests", file: "backends.py" },
  { api: "RetryPolicy per rung · S3StorageBackend.for_backblaze", file: "ladder.py" },
];

const B2_CAPABILITIES = [
  {
    icon: Database,
    title: "Storage plane",
    body: "HIERARCHICAL object layout over the S3 API — runs/{date}/{run}/… plus manifest.json for every asset.",
  },
  {
    icon: Radio,
    title: "Control plane",
    body: "B2 Event Notifications, HMAC-signed, drive an idempotent render→mix→verify→publish stage machine that converges under duplicate and reordered delivery.",
  },
  {
    icon: Lock,
    title: "Immutability plane",
    body: "Object Lock (GOVERNANCE, 30 days) on ci-published/ — verified live by reading back get_object_retention, not claimed.",
  },
];

const RUNBOOK = [
  { step: "01", label: "POST /runs", detail: "script in, chaos optional" },
  { step: "02", label: "fan-out ×3", detail: "narration · music · cover" },
  { step: "03", label: "gate + verify", detail: "AgentLoop → manifest → ID3 embed" },
  { step: "04", label: "B2 event", detail: "HMAC → stage machine" },
  { step: "05", label: "object lock", detail: "immutable publish" },
];

export function Engine() {
  return (
    <section id="engine" className="relative overflow-hidden border-y border-iron bg-coal-900/50">
      <div className="glow-forge absolute inset-0" aria-hidden="true" />

      {/* Surfaces marquee — the integration receipts, on a conveyor */}
      <div className="relative overflow-hidden border-b border-iron bg-coal-950/60 py-3">
        <div className="animate-marquee flex w-max gap-3 pr-3" aria-hidden="true">
          {[...GENBLAZE_SURFACES, ...GENBLAZE_SURFACES].map((s, i) => (
            <span
              key={i}
              className="flex items-center gap-2 whitespace-nowrap rounded-sm border border-iron bg-coal-900/80 px-3 py-1.5 font-mono text-[10.5px] text-iron-text"
            >
              <span className="text-forge-400">{s.api}</span>
              <span className="text-iron-text/60">·</span>
              <span>{s.file}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="relative mx-auto max-w-7xl px-5 py-24 sm:px-8 md:py-32">
        <Reveal className="max-w-3xl">
          <p className="runbook-label">04 / The engine room</p>
          <h2 className="mt-5 font-display text-3xl font-black uppercase leading-[1.08] tracking-tight text-fg sm:text-4xl lg:text-[2.75rem]">
            The SDK is the <span className="text-forge-gradient">engine</span> — not decoration.
          </h2>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-iron-text">
            Nine load-bearing Genblaze surfaces and three distinct Backblaze B2 capabilities, each
            one doing real work in the run path. Remove either half and the differentiator
            collapses.
          </p>
        </Reveal>

        {/* Runbook strip */}
        <Reveal delay={120}>
          <ol className="mt-12 grid grid-cols-1 gap-px overflow-hidden rounded-xl border border-iron bg-iron sm:grid-cols-2 lg:grid-cols-5">
            {RUNBOOK.map((r) => (
              <li key={r.step} className="group bg-coal-950/80 p-5 transition-colors duration-300 hover:bg-coal-850">
                <span className="font-display text-2xl font-black text-stencil transition-colors duration-300 group-hover:text-forge-500/40">
                  {r.step}
                </span>
                <p className="mt-2 font-mono text-xs uppercase tracking-[0.14em] text-fg">{r.label}</p>
                <p className="mt-1 font-mono text-[10.5px] leading-relaxed text-iron-text">{r.detail}</p>
              </li>
            ))}
          </ol>
        </Reveal>

        <div className="mt-14 grid grid-cols-1 gap-10 lg:grid-cols-2">
          {/* Genblaze column */}
          <Reveal>
            <div className="flex items-center gap-3">
              <Badge variant="forge">Genblaze 0.4.1</Badge>
              <span className="font-mono text-[11px] uppercase tracking-widest2 text-iron-text">
                9 surfaces · all in the run path
              </span>
            </div>
            <ul className="mt-5 space-y-2">
              {GENBLAZE_SURFACES.map((s) => (
                <li
                  key={s.api}
                  className="group flex items-center justify-between gap-4 rounded-md border border-iron bg-coal-950/50 px-4 py-2.5 transition-all duration-200 hover:border-forge-500/40 hover:bg-coal-950/80"
                >
                  <code className="font-mono text-[12px] text-fg transition-colors group-hover:text-forge-300">
                    {s.api}
                  </code>
                  <span className="shrink-0 font-mono text-[10px] text-iron-text">{s.file}</span>
                </li>
              ))}
            </ul>
          </Reveal>

          {/* B2 column */}
          <Reveal delay={140}>
            <div className="flex items-center gap-3">
              <Badge variant="b2">Backblaze B2</Badge>
              <span className="font-mono text-[11px] uppercase tracking-widest2 text-iron-text">
                storage · control · immutability
              </span>
            </div>
            <div className="mt-5 space-y-4">
              {B2_CAPABILITIES.map((c) => (
                <Card key={c.title} className="plate-hover group p-5">
                  <div className="flex items-start gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-b2/40 bg-b2/10 text-red-300 transition-transform duration-300 group-hover:scale-110">
                      <c.icon className="h-5 w-5" aria-hidden="true" />
                    </div>
                    <div>
                      <h3 className="font-display text-base font-bold text-fg">{c.title}</h3>
                      <p className="mt-1.5 text-sm leading-relaxed text-iron-text">{c.body}</p>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </Reveal>
        </div>

        {/* Why-only defense */}
        <Reveal delay={200}>
          <blockquote className="relative mt-14 overflow-hidden rounded-xl border border-forge-500/25 bg-forge-500/5 p-8">
            <div className="hazard absolute left-0 top-0 h-1 w-full opacity-50" aria-hidden="true" />
            <p className="max-w-4xl text-base leading-relaxed text-fg sm:text-lg">
              <span className="font-display font-bold text-forge-300">Why only this pair: </span>
              the resilience thesis needs both halves. Genblaze&apos;s provider abstraction is what
              makes a <em>cross-provider</em> ladder and manifest-verified resume possible; B2
              Object Lock is what turns &quot;published&quot; into &quot;provably unaltered.&quot;
              Without Genblaze there is no uniform provider/manifest layer to fail over across —
              without B2, tamper-evidence stops at the file and never reaches storage.
            </p>
          </blockquote>
        </Reveal>
      </div>
    </section>
  );
}
