import type { ReactNode } from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Reveal } from "@/components/reveal";
import { LINKS } from "@/lib/utils";

const FAQS: { q: string; a: ReactNode }[] = [
  {
    q: "Is 96/96 a real number or a marketing number?",
    a: (
      <>
        Real, and reproducible on your machine. Run{" "}
        <code className="font-mono text-forge-300">OFFLINE=1 .venv/bin/python bench.py</code> on a
        fresh clone: fixed seed (SEED=42), zero config, no API keys, and the script exits non-zero
        if any correctness gate fails. 48 healthy trials + 48 forced-outage trials, every episode
        hash-verified. Full per-scenario table in DEMO.md.
      </>
    ),
  },
  {
    q: "What exactly happens when ElevenLabs dies mid-render?",
    a: (
      <>
        The ladder catches the failure on rung 0, steps down to rung 1 (LMNT) — rung 2 (Hume)
        stays armed behind it — and the 3-stage fan-out completes. The manifest records the{" "}
        <em>actual</em> provider used (<code className="font-mono">provider_used: lmnt</code>,{" "}
        <code className="font-mono">fallback_rung: 1</code>), not the requested one, and the
        episode ships hash-verified. The live SSE rail shows the rung step in real time.
      </>
    ),
  },
  {
    q: "Why wasn't Genblaze's built-in fallback enough?",
    a: (
      <>
        Genblaze&apos;s <code className="font-mono">fallback_models</code> retries within a single
        provider — if the vendor itself is down, every fallback model is down with it. CastIron&apos;s{" "}
        <code className="font-mono">LadderTTSProvider</code> fails over across{" "}
        <em>distinct vendors</em> and persists the rung into the run manifest. The gap was filed
        upstream as a dossier issue.
      </>
    ),
  },
  {
    q: "How do you prove an episode wasn't altered after render?",
    a: (
      <>
        Two seals. First, the provenance manifest is embedded inside the MP3 itself (ID3), so
        editing one byte flips <code className="font-mono">verify()</code> to False — the
        tamper-evidence travels with the file. Second, the published object sits under a real B2
        Object Lock (GOVERNANCE, 30 days), so the stored copy can&apos;t be overwritten either.
      </>
    ),
  },
  {
    q: "Why Backblaze B2 specifically, and not any S3 bucket?",
    a: (
      <>
        B2 is used as three planes, not one: HIERARCHICAL object storage over the S3 API,
        HMAC-signed Event Notifications that drive the idempotent publish stage machine, and
        Object Lock that makes &quot;published&quot; mean &quot;provably unaltered&quot; — verified
        live by reading back <code className="font-mono">get_object_retention</code>. Drop B2 and
        the tamper-evidence stops at the file instead of reaching storage.
      </>
    ),
  },
  {
    q: "Can I run it with zero API keys?",
    a: (
      <>
        Yes — that&apos;s the always-green OFFLINE mode:{" "}
        <code className="font-mono text-forge-300">OFFLINE=1</code> swaps in mock providers and a
        local storage backend, no network, no credentials. It&apos;s the dev loop, the deterministic
        regression net behind all 175 tests, and the demo-day disaster fallback — the same code
        path.
      </>
    ),
  },
  {
    q: "What do the latency numbers actually measure?",
    a: (
      <>
        Honest scope: p50 ≈ 120 ms / p95 ≈ 134 ms is OFFLINE <em>orchestration</em> — fan-out,
        manifest verify, and in-file embed with mock providers. Real vendor synthesis time is
        provider-bound and excluded, which is why the headline is the reliability figure (0
        dropped), never a speed claim. Limitations are spelled out in DEMO.md and DEVIATIONS.md.
      </>
    ),
  },
  {
    q: "What stops a retry storm from burning my budget?",
    a: (
      <>
        A budget guard prices the run first: projected cost over{" "}
        <code className="font-mono">MAX_RUN_COST_USD</code> hard-aborts with a typed{" "}
        <code className="font-mono text-danger">BUDGET_ABORT</code> before a cent is spent. And
        transient failures use <code className="font-mono">Pipeline.resume_step</code> — resume,
        single charge, not resubmit.
      </>
    ),
  },
];

export function FAQ() {
  const mid = Math.ceil(FAQS.length / 2);
  const columns = [FAQS.slice(0, mid), FAQS.slice(mid)];

  return (
    <section id="faq" className="relative overflow-hidden border-t border-iron bg-coal-900/50">
      <div className="glow-forge absolute inset-0" aria-hidden="true" />
      <div className="relative mx-auto max-w-7xl px-5 py-24 sm:px-8 md:py-32">
        <Reveal className="max-w-3xl">
          <p className="runbook-label">06 / Interrogation</p>
          <h2 className="mt-5 font-display text-3xl font-black uppercase leading-[1.08] tracking-tight text-fg sm:text-4xl lg:text-[2.75rem]">
            The questions a <span className="text-forge-gradient">skeptical judge</span> should
            ask.
          </h2>
        </Reveal>

        <div className="mt-12 grid grid-cols-1 gap-x-6 gap-y-3 lg:grid-cols-2">
          {columns.map((col, ci) => (
            <Reveal key={ci} delay={ci * 120}>
              <Accordion defaultValue={ci === 0 ? "q-0-0" : null}>
                {col.map((item, i) => (
                  <AccordionItem key={item.q} value={`q-${ci}-${i}`}>
                    <AccordionTrigger>{item.q}</AccordionTrigger>
                    <AccordionContent>{item.a}</AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </Reveal>
          ))}
        </div>

        <Reveal delay={200}>
          <p className="mt-10 font-mono text-[11.5px] uppercase tracking-[0.16em] text-iron-text">
            Still skeptical? Good.{" "}
            <a
              href={LINKS.demoDoc}
              target="_blank"
              rel="noopener noreferrer"
              className="text-ember-400 underline decoration-ember-500/40 underline-offset-4 transition-colors hover:text-ember-300"
            >
              Read the methodology in DEMO.md
            </a>{" "}
            — limitations included.
          </p>
        </Reveal>
      </div>
    </section>
  );
}
