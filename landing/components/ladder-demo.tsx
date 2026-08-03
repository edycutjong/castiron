"use client";

import * as React from "react";
import { ArrowUpRight, RotateCcw, Zap } from "lucide-react";
import { Reveal } from "@/components/reveal";
import { cn, LINKS } from "@/lib/utils";

/**
 * The outage drill — a scripted replay of CastIron's real /console SSE rail.
 * Flip the chaos toggle: rung 0 (ElevenLabs) dies with a 503, the ladder steps
 * down to rung 1 (LMNT), and the episode still ships. Same beats as DEMO.md.
 */

type RungState = "idle" | "active" | "ok" | "down";
type Kind = "cmd" | "info" | "ok" | "fail" | "step" | "ship";

type Step = {
  t: string;
  kind: Kind;
  text: string;
  rungs?: [RungState, RungState, RungState];
  fanDone?: boolean;
  gap: number;
};

const HEALTHY: Step[] = [
  { t: "0.000", kind: "cmd", text: 'POST /runs · {"script":"space_update"}', gap: 350 },
  { t: "0.012", kind: "info", text: "Pipeline.astream(max_concurrency=3) · fan-out ×3 — narration | music | cover", rungs: ["active", "idle", "idle"], gap: 700 },
  { t: "0.081", kind: "ok", text: "narration · rung 0 · elevenlabs — 200 OK", rungs: ["ok", "idle", "idle"], gap: 950 },
  { t: "0.093", kind: "info", text: "gate · LUFS −16.2 ✓ · silence 2.1% ✓ · duration drift 0.4s ✓", fanDone: true, gap: 750 },
  { t: "0.102", kind: "ok", text: "read_manifest(verify=True) ✓ → SmartEmbedder → episode.mp3", gap: 750 },
  { t: "0.110", kind: "info", text: "B2 event notification · HMAC ✓ → stage machine: publish", gap: 700 },
  { t: "0.119", kind: "ship", text: "SHIPPED · ci-published/space_update/episode.mp3 · Object Lock GOVERNANCE +30d", gap: 850 },
];

const CHAOS: Step[] = [
  { t: "0.000", kind: "cmd", text: 'POST /runs · {"script":"space_update","chaos":"tts"}', gap: 350 },
  { t: "0.012", kind: "info", text: "Pipeline.astream(max_concurrency=3) · fan-out ×3 — narration | music | cover", rungs: ["active", "idle", "idle"], gap: 700 },
  { t: "0.058", kind: "fail", text: "narration · rung 0 · elevenlabs — 503 SERVICE UNAVAILABLE", rungs: ["down", "idle", "idle"], gap: 1000 },
  { t: "0.061", kind: "step", text: "LadderTTSProvider · stepping down → rung 1 · lmnt", rungs: ["down", "active", "idle"], gap: 850 },
  { t: "0.096", kind: "ok", text: "narration · rung 1 · lmnt — 200 OK · fell back · rung 1", rungs: ["down", "ok", "idle"], gap: 950 },
  { t: "0.107", kind: "info", text: "gate · LUFS −16.4 ✓ · silence 2.3% ✓ · duration drift 0.6s ✓", fanDone: true, gap: 750 },
  { t: "0.118", kind: "ok", text: "read_manifest(verify=True) ✓ → SmartEmbedder → episode.mp3", gap: 750 },
  { t: "0.126", kind: "info", text: "B2 event notification · HMAC ✓ → stage machine: publish", gap: 700 },
  { t: "0.134", kind: "ship", text: "SHIPPED · ci-published/space_update/episode.mp3 · Object Lock GOVERNANCE +30d", gap: 850 },
];

const RUNGS = [
  { idx: 0, vendor: "elevenlabs", note: "primary" },
  { idx: 1, vendor: "lmnt", note: "failover" },
  { idx: 2, vendor: "hume", note: "last resort" },
];

const PREFIX: Record<Kind, string> = {
  cmd: "$",
  info: "▸",
  ok: "✓",
  fail: "✗",
  step: "⚡",
  ship: "●",
};

const LINE_STYLE: Record<Kind, string> = {
  cmd: "text-fg",
  info: "text-iron-text",
  ok: "text-forge-300",
  fail: "text-red-300",
  step: "text-ember-300",
  ship: "font-bold text-forge-300",
};

export function LadderDemo() {
  const [chaos, setChaos] = React.useState(true);
  const [runId, setRunId] = React.useState(0);
  const [started, setStarted] = React.useState(false);
  const [count, setCount] = React.useState(0);
  const frameRef = React.useRef<HTMLDivElement>(null);

  const steps = chaos ? CHAOS : HEALTHY;

  // Arm the drill when it scrolls into view.
  React.useEffect(() => {
    const el = frameRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setStarted(true);
          io.disconnect();
        }
      },
      { threshold: 0.3 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // Play the rail, line by line.
  React.useEffect(() => {
    if (!started) return;
    setCount(0);
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setCount(steps.length);
      return;
    }
    const timers: number[] = [];
    const schedule = (idx: number) => {
      if (idx >= steps.length) return;
      const id = window.setTimeout(() => {
        setCount(idx + 1);
        schedule(idx + 1);
      }, steps[idx].gap);
      timers.push(id);
    };
    schedule(0);
    return () => timers.forEach((id) => window.clearTimeout(id));
  }, [started, chaos, runId, steps]);

  const revealed = steps.slice(0, count);
  const lastRungs = [...revealed].reverse().find((s) => s.rungs)?.rungs ?? ["idle", "idle", "idle"];
  const fanDone = revealed.some((s) => s.fanDone);
  const fanStarted = revealed.length > 1;
  const shipped = count >= steps.length;

  return (
    <section id="drill" className="relative overflow-hidden border-y border-iron bg-coal-900/50">
      <div className="glow-ember absolute inset-0" aria-hidden="true" />
      <div
        className="pointer-events-none absolute -left-6 top-16 hidden select-none font-display text-[9rem] font-black leading-none text-stencil-ember opacity-60 xl:block"
        aria-hidden="true"
      >
        CHAOS
      </div>

      <div className="relative mx-auto max-w-7xl px-5 py-24 sm:px-8 md:py-32">
        <Reveal className="mx-auto max-w-3xl text-center">
          <p className="runbook-label">02 / The outage drill</p>
          <h2 className="mt-5 font-display text-3xl font-black uppercase leading-[1.08] tracking-tight text-fg sm:text-4xl lg:text-[2.75rem]">
            Kill the provider <span className="text-ember-gradient">yourself.</span>
          </h2>
          <p className="mt-5 text-base leading-relaxed text-iron-text">
            This is a scripted replay of CastIron&apos;s real <code className="font-mono text-forge-300">/console</code>{" "}
            SSE rail — the same beats as the checked-in demo. Flip the chaos toggle and watch the
            ladder step down a rung without dropping the episode.
          </p>
        </Reveal>

        <Reveal delay={150}>
          <div ref={frameRef} className="plate mx-auto mt-12 max-w-5xl overflow-hidden rounded-2xl">
            {/* Console chrome */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-iron bg-coal-950/70 px-5 py-3.5">
              <div className="flex items-center gap-3">
                <div className="flex gap-1.5" aria-hidden="true">
                  <span className="h-2.5 w-2.5 rounded-full bg-danger/70" />
                  <span className="h-2.5 w-2.5 rounded-full bg-ember-500/70" />
                  <span className="h-2.5 w-2.5 rounded-full bg-forge-500/70" />
                </div>
                <span className="hidden font-mono text-[10.5px] uppercase tracking-widest2 text-iron-text sm:inline">
                  castiron · /console — SSE stage rail
                </span>
              </div>

              <div className="flex items-center gap-3">
                {/* The chaos toggle */}
                <button
                  type="button"
                  role="switch"
                  aria-checked={chaos}
                  onClick={() => setChaos((v) => !v)}
                  className={cn(
                    "group flex items-center gap-2.5 rounded-md border px-3 py-1.5 transition-all duration-300",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-400",
                    chaos
                      ? "border-ember-500/60 bg-ember-500/10"
                      : "border-iron-strong bg-coal-850/60 hover:border-iron-strong"
                  )}
                >
                  <span
                    className={cn(
                      "font-mono text-[10.5px] uppercase tracking-widest2 transition-colors",
                      chaos ? "text-ember-300" : "text-iron-text"
                    )}
                  >
                    chaos: tts outage
                  </span>
                  <span
                    className={cn(
                      "relative flex h-5 w-9 items-center rounded-full border transition-colors duration-300",
                      chaos ? "border-ember-500/70 bg-ember-500/30" : "border-iron-strong bg-coal-800"
                    )}
                    aria-hidden="true"
                  >
                    <span
                      className={cn(
                        "absolute h-3.5 w-3.5 rounded-full transition-all duration-300",
                        chaos
                          ? "left-[calc(100%-1.1rem)] bg-ember-400 shadow-[0_0_10px_rgba(245,158,11,0.8)]"
                          : "left-0.5 bg-iron-text"
                      )}
                    />
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => setRunId((n) => n + 1)}
                  aria-label="Replay the run"
                  className="inline-flex h-8 items-center gap-1.5 rounded-md border border-iron-strong px-2.5 font-mono text-[10.5px] uppercase tracking-widest2 text-iron-text transition-colors duration-200 hover:border-forge-500/60 hover:text-forge-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-400"
                >
                  <RotateCcw className="h-3 w-3" aria-hidden="true" />
                  replay
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-[0.92fr_1.08fr]">
              {/* Left: the failover ladder */}
              <div className="border-b border-iron bg-coal-950/40 p-6 lg:border-b-0 lg:border-r">
                <p className="runbook-label mb-4">narration · failover ladder</p>
                <ul className="space-y-2.5">
                  {RUNGS.map((rung) => {
                    const state = lastRungs[rung.idx];
                    return (
                      <li key={rung.idx}>
                        {rung.idx === 1 && chaos && state !== "idle" && (
                          <div className="mb-2.5 ml-4 flex items-center gap-2 text-ember-400">
                            <span className="h-4 w-px bg-ember-500/60" aria-hidden="true" />
                            <Zap className="h-3.5 w-3.5" aria-hidden="true" />
                            <span className="font-mono text-[10px] uppercase tracking-widest2">
                              ladder steps down
                            </span>
                          </div>
                        )}
                        <div
                          className={cn(
                            "flex items-center justify-between gap-3 rounded-lg border px-4 py-3 transition-all duration-500",
                            state === "idle" && "border-iron bg-coal-900/40 opacity-60",
                            state === "active" && "border-forge-500/50 bg-forge-500/5",
                            state === "ok" && "border-forge-500/60 bg-forge-500/10",
                            state === "down" && "border-danger/50 bg-danger/5"
                          )}
                        >
                          <div className="flex items-center gap-3">
                            <span
                              className={cn(
                                "grid h-7 w-7 place-items-center rounded-sm border font-mono text-[11px]",
                                state === "down"
                                  ? "border-danger/50 text-danger"
                                  : state === "idle"
                                    ? "border-iron-strong text-iron-text"
                                    : "border-forge-500/60 text-forge-300"
                              )}
                            >
                              {rung.idx}
                            </span>
                            <div className="leading-tight">
                              <p
                                className={cn(
                                  "font-mono text-[13px]",
                                  state === "down" ? "text-red-300 line-through" : "text-fg"
                                )}
                              >
                                {rung.vendor}
                              </p>
                              <p className="mt-0.5 font-mono text-[9.5px] uppercase tracking-widest2 text-iron-text">
                                {rung.note}
                              </p>
                            </div>
                          </div>
                          <span
                            className={cn(
                              "rounded-sm border px-2 py-1 font-mono text-[9.5px] uppercase tracking-[0.14em] transition-all duration-300",
                              state === "idle" && "border-iron-strong text-iron-text",
                              state === "active" && "animate-pulse border-forge-500/60 text-forge-300",
                              state === "ok" && "border-forge-500/60 bg-forge-500/10 text-forge-300",
                              state === "down" && "border-danger/60 bg-danger/10 text-red-300"
                            )}
                          >
                            {state === "idle" && "standby"}
                            {state === "active" && "rendering"}
                            {state === "ok" && "200 ok"}
                            {state === "down" && "503 down"}
                          </span>
                        </div>
                      </li>
                    );
                  })}
                </ul>

                {/* Parallel fan-out lanes */}
                <p className="runbook-label mb-3 mt-7">parallel fan-out</p>
                <div className="grid grid-cols-3 gap-2">
                  {["narration", "music", "cover"].map((lane) => {
                    const laneOk =
                      lane === "narration"
                        ? lastRungs.includes("ok")
                        : fanDone;
                    const laneActive = fanStarted && !laneOk;
                    return (
                      <div
                        key={lane}
                        className={cn(
                          "rounded-md border px-2 py-2 text-center font-mono text-[10px] uppercase tracking-[0.12em] transition-all duration-500",
                          laneOk
                            ? "border-forge-500/50 bg-forge-500/10 text-forge-300"
                            : laneActive
                              ? "animate-pulse border-iron-strong text-iron-text"
                              : "border-iron text-iron-text/60"
                        )}
                      >
                        {lane} {laneOk ? "✓" : ""}
                      </div>
                    );
                  })}
                </div>

                {/* Manifest verdict */}
                <div
                  className={cn(
                    "mt-7 rounded-lg border p-4 font-mono text-[11.5px] leading-relaxed transition-all duration-700",
                    shipped
                      ? "border-forge-500/50 bg-forge-500/5 opacity-100"
                      : "border-iron opacity-40"
                  )}
                  aria-live="polite"
                >
                  <p className="runbook-label mb-2">manifest — the actual provider, not the requested one</p>
                  <p className="text-iron-text">
                    provider_used = <span className={chaos ? "text-ember-300" : "text-forge-300"}>&quot;{chaos ? "lmnt" : "elevenlabs"}&quot;</span>
                  </p>
                  <p className="text-iron-text">
                    fallback_rung = <span className={chaos ? "text-ember-300" : "text-forge-300"}>{chaos ? "1" : "0"}</span>
                  </p>
                  <p className="text-iron-text">
                    verify() = <span className="text-forge-300">{shipped ? "True" : "…"}</span> · dropped ={" "}
                    <span className="text-forge-300">0</span>
                  </p>
                </div>
              </div>

              {/* Right: the SSE rail */}
              <div className="bg-coal-950/70 p-6">
                <div className="min-h-[21rem] font-mono text-[12px] leading-[1.9] sm:text-[12.5px]">
                  {revealed.map((step, i) => (
                    <div
                      key={`${chaos ? "c" : "h"}-${runId}-${i}`}
                      className={cn(
                        "flex min-w-0 animate-rise gap-3",
                        step.kind === "ship" && "mt-2 border-t border-iron pt-2"
                      )}
                    >
                      <span className="w-12 shrink-0 text-right text-iron-text/50">+{step.t}</span>
                      <span
                        className={cn(
                          "w-4 shrink-0 text-center",
                          step.kind === "fail" && "text-danger",
                          step.kind === "step" && "text-ember-400",
                          (step.kind === "ok" || step.kind === "ship") && "text-forge-400",
                          step.kind === "cmd" && "text-forge-400",
                          step.kind === "info" && "text-iron-text/70"
                        )}
                        aria-hidden="true"
                      >
                        {PREFIX[step.kind]}
                      </span>
                      <span
                        className={cn("min-w-0 break-words [overflow-wrap:anywhere]", LINE_STYLE[step.kind])}
                      >
                        {step.text}
                      </span>
                    </div>
                  ))}
                  <div className="flex gap-3">
                    <span className="w-12 shrink-0" />
                    <span className="w-4 shrink-0" />
                    <span className="inline-block h-4 w-2.5 animate-blink bg-forge-400/80" aria-hidden="true" />
                  </div>
                </div>

                <p
                  className={cn(
                    "mt-4 border-t border-iron pt-4 font-mono text-[10.5px] uppercase tracking-widest2 transition-opacity duration-700",
                    shipped ? "opacity-100" : "opacity-0"
                  )}
                >
                  <span className="text-forge-400">ALL GREEN — 0 dropped episodes.</span>{" "}
                  <span className="text-iron-text">
                    {chaos
                      ? "outage caught on rung 0 · shipped via rung 1"
                      : "no outage · shipped via rung 0"}
                  </span>
                </p>
              </div>
            </div>
          </div>
        </Reveal>

        <Reveal delay={250} className="mx-auto mt-8 flex max-w-5xl flex-col items-center justify-between gap-4 sm:flex-row">
          <p className="font-mono text-[11px] leading-relaxed text-iron-text">
            Proven 48/48 forced-outage trials in the seeded benchmark — the primary provider is
            killed on <span className="text-fg">every</span> failover trial.
          </p>
          <a
            href={LINKS.console}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex shrink-0 items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-ember-400 transition-colors hover:text-ember-300"
          >
            Run it live at api.castiron.edycu.dev/console
            <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
          </a>
        </Reveal>
      </div>
    </section>
  );
}
