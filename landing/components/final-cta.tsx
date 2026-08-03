import { ArrowUpRight, Check, FileText } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { CopyButton } from "@/components/copy-button";
import { Reveal } from "@/components/reveal";
import { BENCH_CMD, LINKS } from "@/lib/utils";

const MICRO_PROOF = [
  "Zero API keys needed offline",
  "Seeded — same numbers every run",
  "Exits non-zero on any failure",
];

export function FinalCTA() {
  return (
    <section id="ship" className="relative overflow-hidden">
      {/* Hazard rails top & bottom — the last-chance klaxon */}
      <div className="hazard h-2 w-full opacity-80" aria-hidden="true" />

      <div className="relative border-b border-iron bg-coal-950">
        <div className="bg-blueprint absolute inset-0" aria-hidden="true" />
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 70% 60% at 50% 110%, rgba(245,158,11,0.18), transparent 65%), radial-gradient(ellipse 50% 40% at 50% -10%, rgba(16,185,129,0.1), transparent 70%)",
          }}
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute inset-x-0 top-1/2 -translate-y-1/2 select-none text-center font-display text-[16vw] font-black leading-none text-stencil-ember opacity-30"
          aria-hidden="true"
        >
          SHIP
        </div>

        <div className="relative mx-auto max-w-4xl px-5 py-28 text-center sm:px-8 md:py-36">
          <Reveal>
            <p className="runbook-label">07 / Your move</p>
            <h2 className="mt-6 font-display text-[clamp(2.2rem,7vw,4.5rem)] font-black uppercase leading-[1.02] tracking-tight">
              <span className="block text-fg">Kill a provider.</span>
              <span className="text-ember-gradient block">Ship anyway.</span>
            </h2>
            <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-iron-text sm:text-lg">
              Open the live console, flip the chaos toggle, and watch a real run step down the
              ladder — or clone the repo and make the benchmark prove it to you.
            </p>
          </Reveal>

          <Reveal delay={150}>
            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <a
                href={LINKS.console}
                target="_blank"
                rel="noopener noreferrer"
                className={buttonVariants({
                  variant: "molten",
                  size: "xl",
                  className: "animate-ember-pulse w-full sm:w-auto",
                })}
              >
                Open the live console
                <ArrowUpRight className="h-5 w-5" />
              </a>
              <a
                href={LINKS.demoDoc}
                target="_blank"
                rel="noopener noreferrer"
                className={buttonVariants({ variant: "iron", size: "xl", className: "w-full sm:w-auto" })}
              >
                <FileText className="h-4 w-4" />
                Read DEMO.md
              </a>
            </div>
          </Reveal>

          <Reveal delay={250}>
            <div className="mx-auto mt-8 flex max-w-lg items-center justify-between gap-3 rounded-lg border border-iron bg-coal-900/80 py-2.5 pl-5 pr-2.5 backdrop-blur">
              <code className="truncate text-left font-mono text-xs text-iron-text sm:text-[13px]">
                <span className="text-forge-400">$</span> {BENCH_CMD}
              </code>
              <CopyButton text={BENCH_CMD} />
            </div>

            <ul className="mt-6 flex flex-wrap items-center justify-center gap-x-7 gap-y-2.5">
              {MICRO_PROOF.map((p) => (
                <li key={p} className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.14em] text-iron-text">
                  <Check className="h-3.5 w-3.5 text-forge-400" aria-hidden="true" />
                  {p}
                </li>
              ))}
            </ul>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
