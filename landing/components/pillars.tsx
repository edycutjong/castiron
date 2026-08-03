import { Activity, CircleDollarSign, CloudOff, Fingerprint, Lock, Zap } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Reveal } from "@/components/reveal";
import { cn } from "@/lib/utils";

function IconTile({
  icon: Icon,
  tone,
}: {
  icon: typeof Zap;
  tone: "forge" | "ember" | "danger";
}) {
  return (
    <div
      className={cn(
        "flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border transition-transform duration-300 group-hover:scale-110",
        tone === "forge" && "border-forge-500/40 bg-gradient-to-b from-forge-500/20 to-forge-600/5 text-forge-300",
        tone === "ember" && "border-ember-500/40 bg-gradient-to-b from-ember-500/20 to-ember-600/5 text-ember-300",
        tone === "danger" && "border-danger/40 bg-gradient-to-b from-danger/20 to-danger/5 text-red-300"
      )}
    >
      <Icon className="h-5 w-5" aria-hidden="true" />
    </div>
  );
}

export function Pillars() {
  return (
    <section id="pillars" className="relative overflow-hidden">
      <div className="bg-blueprint-fine absolute inset-0 opacity-50" aria-hidden="true" />
      <div className="relative mx-auto max-w-7xl px-5 py-24 sm:px-8 md:py-32">
        <Reveal className="max-w-3xl">
          <p className="runbook-label">03 / What makes it unkillable</p>
          <h2 className="mt-5 font-display text-3xl font-black uppercase leading-[1.08] tracking-tight text-fg sm:text-4xl lg:text-[2.75rem]">
            Failure is the <span className="text-forge-gradient">default path</span> — so every
            stage is armored.
          </h2>
        </Reveal>

        <div className="mt-14 grid grid-cols-1 gap-4 md:grid-cols-6">
          {/* 1 — Cross-provider failover ladder (the headliner) */}
          <Reveal className="md:col-span-4">
            <Card className="plate-hover group h-full p-7">
              <div className="flex flex-wrap items-start justify-between gap-6">
                <div className="max-w-md">
                  <IconTile icon={Zap} tone="ember" />
                  <h3 className="mt-5 font-display text-xl font-bold text-fg">
                    Cross-provider failover ladder
                  </h3>
                  <p className="mt-3 text-sm leading-relaxed text-iron-text">
                    Every narration render tries <span className="text-fg">distinct vendors</span> in
                    order — ElevenLabs &rarr; LMNT &rarr; Hume. One dies mid-render, the ladder steps
                    down a rung and the run keeps moving. CastIron&apos;s own primitive: Genblaze&apos;s
                    built-in <code className="font-mono text-[12px] text-forge-300">fallback_models</code>{" "}
                    is in-provider only (gap filed upstream).
                  </p>
                </div>
                {/* Mini ladder diagram */}
                <div className="w-full max-w-[220px] font-mono text-[11px]" aria-hidden="true">
                  {[
                    { name: "elevenlabs", state: "down" },
                    { name: "lmnt", state: "via" },
                    { name: "hume", state: "standby" },
                  ].map((r, i) => (
                    <div key={r.name}>
                      {i === 1 && (
                        <div className="my-1 ml-3 flex items-center gap-1.5 text-ember-400">
                          <span className="h-3 w-px bg-ember-500/60" />
                          <Zap className="h-3 w-3" />
                        </div>
                      )}
                      <div
                        className={cn(
                          "flex items-center justify-between rounded-md border px-3 py-2",
                          r.state === "down" && "border-danger/40 text-red-300",
                          r.state === "via" && "border-ember-500/50 bg-ember-500/10 text-ember-300",
                          r.state === "standby" && "border-iron text-iron-text/70"
                        )}
                      >
                        <span className={r.state === "down" ? "line-through" : ""}>{r.name}</span>
                        <span className="text-[9px] uppercase tracking-[0.14em]">
                          {r.state === "down" ? "503" : r.state === "via" ? "shipped via" : "armed"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          </Reveal>

          {/* 2 — Provenance in the file */}
          <Reveal delay={100} className="md:col-span-2">
            <Card className="plate-hover group h-full p-7">
              <IconTile icon={Fingerprint} tone="forge" />
              <h3 className="mt-5 font-display text-xl font-bold text-fg">
                Provenance hashed into the file
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-iron-text">
                The manifest is embedded <span className="text-fg">inside the MP3</span> (ID3).
                Edit one byte and{" "}
                <code className="font-mono text-[12px] text-danger">verify() → False</code>.
                Tamper-evidence travels with the episode.
              </p>
            </Card>
          </Reveal>

          {/* 3 — Immutable publish */}
          <Reveal className="md:col-span-2">
            <Card className="plate-hover group h-full p-7">
              <IconTile icon={Lock} tone="forge" />
              <h3 className="mt-5 font-display text-xl font-bold text-fg">Immutable publish</h3>
              <p className="mt-3 text-sm leading-relaxed text-iron-text">
                Episodes land in Backblaze B2 under a real{" "}
                <span className="text-fg">Object Lock</span> —{" "}
                <code className="font-mono text-[12px] text-forge-300">GOVERNANCE +30d</code>, proven
                by reading the retention back from a live bucket. Published means provably unaltered.
              </p>
            </Card>
          </Reveal>

          {/* 4 — Self-healing gate */}
          <Reveal delay={100} className="md:col-span-2">
            <Card className="plate-hover group h-full p-7">
              <IconTile icon={Activity} tone="forge" />
              <h3 className="mt-5 font-display text-xl font-bold text-fg">
                Self-healing quality gate
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-iron-text">
                An AgentLoop evaluator iterates the narration until it passes a{" "}
                <span className="text-fg">LUFS band, silence ratio, and duration drift</span> — and
                transient failures resume with a single charge, not a resubmit.
              </p>
            </Card>
          </Reveal>

          {/* 5 — Budget guard */}
          <Reveal delay={200} className="md:col-span-2">
            <Card className="plate-hover group h-full p-7">
              <IconTile icon={CircleDollarSign} tone="danger" />
              <h3 className="mt-5 font-display text-xl font-bold text-fg">Budget hard-abort</h3>
              <p className="mt-3 text-sm leading-relaxed text-iron-text">
                A run projected over{" "}
                <code className="font-mono text-[12px] text-fg">MAX_RUN_COST_USD</code> aborts{" "}
                <span className="text-fg">before spending</span>, with a typed{" "}
                <code className="font-mono text-[12px] text-danger">BUDGET_ABORT</code> — no
                surprise invoices from a retry storm.
              </p>
            </Card>
          </Reveal>

          {/* 6 — Always-green OFFLINE mode (wide strip) */}
          <Reveal className="md:col-span-6">
            <Card className="plate-hover group p-7">
              <div className="flex flex-col items-start gap-6 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex items-start gap-5">
                  <IconTile icon={CloudOff} tone="ember" />
                  <div className="max-w-xl">
                    <h3 className="font-display text-xl font-bold text-fg">
                      Always-green OFFLINE mode
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-iron-text">
                      Mock providers + a local backend give a zero-network, zero-credential path —
                      the dev loop, the deterministic regression net, and the demo-day disaster
                      fallback are the same code.
                    </p>
                  </div>
                </div>
                <code className="rounded-md border border-forge-500/30 bg-coal-950/80 px-4 py-3 font-mono text-[11.5px] text-iron-text">
                  <span className="text-forge-400">$</span> OFFLINE=1 verify_offline.py{" "}
                  <span className="text-forge-300">→ &quot;ALL GREEN — 0 dropped episodes&quot;</span>
                </code>
              </div>
            </Card>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
