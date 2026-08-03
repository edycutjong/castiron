import { ArrowUpRight, Github, Radio } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { CountUp } from "@/components/count-up";
import { CopyButton } from "@/components/copy-button";
import { BENCH_CMD, LINKS } from "@/lib/utils";

const STATS: { value: number; render: string; label: string; tone: string }[] = [
  { value: 96, render: "/96", label: "episodes shipped hash-verified", tone: "text-forge-400" },
  { value: 0, render: "", label: "dropped — healthy + forced-outage runs", tone: "text-ember-400" },
  { value: 175, render: "", label: "tests passing · 100% line coverage", tone: "text-fg" },
  { value: 134, render: "ms", label: "p95 failover orchestration (offline)", tone: "text-fg" },
];

export function Hero() {
  return (
    <section id="top" className="relative overflow-hidden pt-[4.25rem]">
      {/* Atmosphere: blueprint grid + forge/ember glows + ghost stencil */}
      <div className="bg-blueprint absolute inset-0" aria-hidden="true" />
      <div className="glow-forge absolute inset-0" aria-hidden="true" />
      <div className="glow-ember absolute inset-0" aria-hidden="true" />
      <div
        className="pointer-events-none absolute -right-10 bottom-24 hidden select-none font-display text-[11rem] font-black leading-none tracking-tight text-stencil xl:block"
        aria-hidden="true"
      >
        0&nbsp;DROPPED
      </div>

      <div className="relative mx-auto max-w-7xl px-5 pb-10 pt-16 sm:px-8 md:pt-24">
        <div className="grid grid-cols-1 items-center gap-14 lg:grid-cols-[1.15fr_0.85fr]">
          {/* Left — the claim */}
          <div className="hero-stagger">
            <div className="flex flex-wrap items-center gap-2.5">
              <Badge variant="ember">
                <Radio className="h-3 w-3" aria-hidden="true" />
                Backblaze Generative Media Hackathon
              </Badge>
              <Badge variant="iron">Genblaze 0.4.1 + B2 · MIT</Badge>
            </div>

            {/* Element 3: massive SEO title */}
            <h1 className="mt-7 font-display text-[clamp(2.1rem,6.2vw,4.6rem)] font-black uppercase leading-[1.04] tracking-tight">
              <span className="block text-fg">
                Your TTS provider{" "}
                <span className="relative inline-block text-danger">
                  just died.
                  <span
                    className="hazard-danger absolute -bottom-1 left-0 h-[5px] w-full opacity-70"
                    aria-hidden="true"
                  />
                </span>
              </span>
              <span className="text-forge-gradient mt-3 block">The episode still ships.</span>
            </h1>

            <p className="mt-7 max-w-xl text-base leading-relaxed text-iron-text sm:text-lg">
              CastIron is a self-healing audio-episode factory: hand it a script and it fans out
              narration, music, and cover art in parallel. When a voice provider goes dark
              mid-render, a <span className="text-fg">cross-provider failover ladder</span>{" "}
              (ElevenLabs&nbsp;&rarr;&nbsp;LMNT&nbsp;&rarr;&nbsp;Hume) steps down a rung — and the
              episode still lands on <span className="text-fg">Backblaze B2</span>, hash-verified,
              Object-Locked, with provenance sealed inside the MP3.
            </p>

            {/* Element 4: primary CTA */}
            <div className="mt-9 flex flex-col gap-3.5 sm:flex-row sm:items-center">
              <a
                href={LINKS.console}
                target="_blank"
                rel="noopener noreferrer"
                className={buttonVariants({
                  variant: "molten",
                  size: "lg",
                  className: "animate-ember-pulse",
                })}
              >
                Watch it survive an outage
                <ArrowUpRight className="h-4 w-4" />
              </a>
              <a
                href={LINKS.repo}
                target="_blank"
                rel="noopener noreferrer"
                className={buttonVariants({ variant: "iron", size: "lg" })}
              >
                <Github className="h-4 w-4" />
                Source on GitHub
              </a>
            </div>

            {/* Reproducibility chip — the honest flex */}
            <div className="mt-5 inline-flex max-w-full items-center gap-3 rounded-md border border-iron bg-coal-900/70 py-2 pl-4 pr-2">
              <code className="truncate font-mono text-[11.5px] text-iron-text sm:text-xs">
                <span className="text-forge-400">$</span> {BENCH_CMD}
              </code>
              <CopyButton text={BENCH_CMD} />
            </div>
          </div>

          {/* Right — the receipt: a real manifest, tilted on the drafting table */}
          <div className="relative hidden lg:block" aria-hidden="true">
            <div
              className="plate animate-float-slow rounded-xl p-6 font-mono text-[12.5px] leading-relaxed"
              style={{ ["--tilt" as string]: "1.6deg" }}
            >
              <div className="mb-4 flex items-center justify-between border-b border-iron pb-3">
                <span className="text-[10px] uppercase tracking-widest2 text-iron-text">
                  episode.mp3 · in-file ID3 manifest
                </span>
                <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-widest2 text-forge-400">
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-signal-ping rounded-full bg-forge-500" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-forge-400" />
                  </span>
                  verify()=True
                </span>
              </div>
              <pre className="whitespace-pre-wrap text-iron-text">
{`{
  "run": "space_update-0042",
  "requested":     "elevenlabs",`}
                <span className="block text-danger">{`  // rung 0 — 503 mid-render`}</span>
                <span className="block text-ember-400">{`  "provider_used": "lmnt",
  "fallback_rung": 1,`}</span>
{`  "sha256": "9f2c…verified",
  "publish": {
    "bucket": "ci-published",`}
                <span className="block text-forge-400">{`    "object_lock": "GOVERNANCE +30d"`}</span>
{`  }
}`}
              </pre>
            </div>
            <div className="hazard absolute -bottom-3 left-8 right-8 h-1.5 rounded-full opacity-60" />
          </div>
        </div>

        {/* Element 5: social proof — machine-verified numbers, counted up */}
        <dl className="mt-16 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-iron bg-iron md:grid-cols-4">
          {STATS.map((s) => (
            <div key={s.label} className="bg-coal-900/90 px-6 py-6 backdrop-blur-sm">
              <dd className={`font-display text-3xl font-black tracking-tight sm:text-4xl ${s.tone}`}>
                <CountUp value={s.value} suffix={s.render} />
              </dd>
              <dt className="mt-2 font-mono text-[10.5px] uppercase leading-relaxed tracking-[0.14em] text-iron-text">
                {s.label}
              </dt>
            </div>
          ))}
        </dl>
        <p className="mt-3 font-mono text-[10.5px] leading-relaxed text-iron-text/80">
          * Benchmarked by the checked-in <span className="text-iron-text">bench.py</span>, seeded
          (SEED=42), exits non-zero on any correctness failure. Latency is OFFLINE orchestration —
          vendor synthesis excluded. Full methodology in DEMO.md.
        </p>
      </div>

      {/* Element 6 opener: the real animated brand film-strip from the repo */}
      <div className="relative border-y border-iron bg-coal-900/60">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="brand/hero-strip.svg"
          alt="Animated pipeline diagram: the TTS provider dies mid-run, CastIron reroutes to the next rung, the quality gate passes, and the episode is sealed on Backblaze B2 with the fallback recorded in the manifest"
          className="mx-auto w-full max-w-7xl"
          width={1280}
          height={320}
          loading="lazy"
        />
      </div>
    </section>
  );
}
