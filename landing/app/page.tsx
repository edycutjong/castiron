/**
 * CastIron landing — AESTHETIC DIRECTION: "FOUNDRY CONTROL ROOM"
 * ----------------------------------------------------------------
 * One bold direction, executed everywhere:
 *   · Industrial retro-futurist ops console: iron-black plates (#070B0E),
 *     blueprint grids, film-grain noise, hazard-stripe rails.
 *   · Two signal colors only — emerald "ALL GREEN" telemetry (#10B981, brand)
 *     and molten-amber failover heat (#F59E0B, CTAs + chaos). Outage red is
 *     reserved for the failure moment itself.
 *   · Type system: Unbounded (black-weight display, stamped uppercase),
 *     Space Grotesk (body), JetBrains Mono (telemetry, runbook labels).
 *   · Motion: staggered hero forge-in, scroll reveals, count-up gauges, a
 *     scripted SSE-rail replay with a live chaos toggle, ember-pulse CTAs.
 *     All gated behind prefers-reduced-motion.
 *   · Layout: asymmetric drafting-table compositions, runbook-numbered
 *     sections (01–07), ghost stencil type stamped on the plates.
 *
 * The 11 essential elements map:
 *   1 URL keywords → castiron.edycu.dev + descriptive #anchors + metadata
 *   2 Logo         → Header (animated brand mark, top-left)
 *   3 Title/sub    → Hero (massive display type)
 *   4 Primary CTA  → Hero molten button → live console
 *   5 Social proof → Hero count-up stat gauges (machine-verified numbers)
 *   6 Media        → Animated brand film-strip + interactive outage drill
 *   7 Benefits     → Pillars bento (6 armored capabilities)
 *   8 Testimonials → Receipts (quotes from bench.py, pytest, B2, CI)
 *   9 FAQ          → Interrogation accordion (8 skeptical-judge questions)
 *  10 Final CTA    → "Kill a provider. Ship anyway." hazard section
 *  11 Footer       → Contact, legal (MIT), event + proof links
 */
import { Header } from "@/components/header";
import { Hero } from "@/components/hero";
import { Problem } from "@/components/problem";
import { LadderDemo } from "@/components/ladder-demo";
import { Pillars } from "@/components/pillars";
import { Engine } from "@/components/engine";
import { Receipts } from "@/components/receipts";
import { FAQ } from "@/components/faq";
import { FinalCTA } from "@/components/final-cta";
import { Footer } from "@/components/footer";

export default function Page() {
  return (
    <>
      <a
        href="#top-content"
        className="fixed left-4 top-4 z-[100] -translate-y-24 rounded-md border border-forge-500/60 bg-coal-950 px-4 py-2.5 font-mono text-xs uppercase tracking-widest2 text-forge-300 shadow-2xl transition-transform duration-200 focus:translate-y-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-400"
      >
        Skip to content
      </a>
      <Header />
      <main id="top-content">
        <Hero />
        <Problem />
        <LadderDemo />
        <Pillars />
        <Engine />
        <Receipts />
        <FAQ />
        <FinalCTA />
      </main>
      <Footer />
    </>
  );
}
