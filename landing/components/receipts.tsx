import { FileAudio2, FlaskConical, GitBranch, Lock, ShieldCheck, TerminalSquare } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Reveal } from "@/components/reveal";
import { cn } from "@/lib/utils";

/**
 * Element 8, reforged: no invented humans on a hackathon page.
 * These are real outputs from the machines in the pipeline — each quote is a
 * verbatim (or lightly abridged) artifact a judge can regenerate.
 */
const RECEIPTS = [
  {
    icon: TerminalSquare,
    quote:
      "HEADLINE: 96/96 episodes shipped hash-verified across healthy + forced-outage runs — 0 dropped.",
    name: "bench.py",
    role: "seeded benchmark · SEED=42 · exits non-zero on failure",
    tone: "forge" as const,
    big: true,
  },
  {
    icon: FileAudio2,
    quote: "provider_used = lmnt · fallback_rung = 1 — the vendor that actually rendered, not the one requested.",
    name: "episode.mp3",
    role: "in-file ID3 manifest, read back via /runs/{id}",
    tone: "ember" as const,
  },
  {
    icon: Lock,
    quote: "Mode=GOVERNANCE · RetainUntilDate=+30d — retention read back from the live bucket, not claimed.",
    name: "b2 · get_object_retention",
    role: "Backblaze B2 Object Lock, live evidence pack p3",
    tone: "forge" as const,
  },
  {
    icon: ShieldCheck,
    quote: "Flip one byte of the sealed provenance and verify() returns False. Every time.",
    name: "verify()",
    role: "tamper trial — DEMO.md scenario 3",
    tone: "ember" as const,
  },
  {
    icon: FlaskConical,
    quote: "175 passed. 100% line coverage on castiron/. Ruff clean.",
    name: "pytest",
    role: "OFFLINE=1 deterministic regression net",
    tone: "forge" as const,
  },
  {
    icon: GitBranch,
    quote: "Quality → Security → Build → E2E → Performance → Deploy: green. CodeQL + Dependabot + secret scanning: 0 open alerts.",
    name: "GitHub Actions",
    role: "6-stage CI/CD pipeline on main",
    tone: "forge" as const,
  },
];

function ReliabilityBlocks({ tone }: { tone: "forge" | "ember" }) {
  return (
    <div className="flex gap-1" role="img" aria-label="Reliability rating: 5 out of 5">
      {Array.from({ length: 5 }).map((_, i) => (
        <span
          key={i}
          className={cn(
            "h-2 w-3.5 skew-x-[-12deg]",
            tone === "forge" ? "bg-forge-500" : "bg-ember-500"
          )}
        />
      ))}
    </div>
  );
}

export function Receipts() {
  return (
    <section id="receipts" className="relative overflow-hidden">
      <div className="bg-blueprint-fine absolute inset-0 opacity-50" aria-hidden="true" />
      <div
        className="pointer-events-none absolute -right-8 top-20 hidden select-none font-display text-[10rem] font-black leading-none text-stencil opacity-70 xl:block"
        aria-hidden="true"
      >
        96/96
      </div>

      <div className="relative mx-auto max-w-7xl px-5 py-24 sm:px-8 md:py-32">
        <Reveal className="max-w-3xl">
          <p className="runbook-label">05 / Receipts</p>
          <h2 className="mt-5 font-display text-3xl font-black uppercase leading-[1.08] tracking-tight text-fg sm:text-4xl lg:text-[2.75rem]">
            Testimonials from things that{" "}
            <span className="text-ember-gradient">cannot flatter you.</span>
          </h2>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-iron-text">
            A weekend project doesn&apos;t have customers — it has evidence. Every quote below is a
            real artifact of the pipeline, and every one can be regenerated from a fresh clone.
          </p>
        </Reveal>

        <div className="mt-14 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {RECEIPTS.map((r, i) => (
            <Reveal key={r.name} delay={(i % 3) * 110} className={r.big ? "md:col-span-2 lg:col-span-1" : ""}>
              <Card className="plate-hover group flex h-full flex-col p-6">
                <div className="flex items-center justify-between">
                  <span
                    className={cn(
                      "font-mono text-4xl leading-none",
                      r.tone === "forge" ? "text-forge-500/50" : "text-ember-500/50"
                    )}
                    aria-hidden="true"
                  >
                    &gt;_
                  </span>
                  <ReliabilityBlocks tone={r.tone} />
                </div>
                <blockquote
                  className={cn(
                    "mt-5 grow font-mono text-[13px] leading-relaxed",
                    r.big ? "text-forge-300" : "text-fg/90"
                  )}
                >
                  &ldquo;{r.quote}&rdquo;
                </blockquote>
                <footer className="mt-6 flex items-center gap-3 border-t border-iron pt-4">
                  <div
                    className={cn(
                      "flex h-9 w-9 shrink-0 items-center justify-center rounded-md border transition-transform duration-300 group-hover:scale-110",
                      r.tone === "forge"
                        ? "border-forge-500/40 bg-forge-500/10 text-forge-300"
                        : "border-ember-500/40 bg-ember-500/10 text-ember-300"
                    )}
                  >
                    <r.icon className="h-4 w-4" aria-hidden="true" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate font-mono text-xs font-semibold text-fg">{r.name}</p>
                    <p className="font-mono text-[10px] uppercase leading-relaxed tracking-[0.12em] text-iron-text">
                      {r.role}
                    </p>
                  </div>
                </footer>
              </Card>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
