import { ArrowUpRight, Github, Radio, Scale } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { LINKS } from "@/lib/utils";

const COLUMNS: { title: string; links: { label: string; href: string; external?: boolean }[] }[] = [
  {
    title: "Product",
    links: [
      { label: "Live console (/console)", href: LINKS.console, external: true },
      { label: "API — api.castiron.edycu.dev", href: LINKS.api, external: true },
      { label: "Product home — castiron.edycu.dev", href: LINKS.product, external: true },
      { label: "Pitch deck", href: LINKS.pitch, external: true },
    ],
  },
  {
    title: "Proof",
    links: [
      { label: "DEMO.md — benchmark methodology", href: LINKS.demoDoc, external: true },
      { label: "README — architecture & SDK map", href: LINKS.readme, external: true },
      { label: "Releases", href: LINKS.releases, external: true },
      { label: "File an issue", href: LINKS.issues, external: true },
    ],
  },
  {
    title: "Event",
    links: [
      { label: "Backblaze Generative Media Hackathon", href: LINKS.devpost, external: true },
      { label: "Backblaze B2 Cloud Storage", href: LINKS.backblaze, external: true },
      { label: "Source on GitHub", href: LINKS.repo, external: true },
      { label: "MIT License", href: LINKS.license, external: true },
    ],
  },
];

export function Footer() {
  return (
    <footer className="relative bg-coal-950">
      <div className="mx-auto max-w-7xl px-5 py-16 sm:px-8">
        <div className="grid grid-cols-1 gap-12 lg:grid-cols-[1.2fr_2fr]">
          {/* Brand block */}
          <div>
            <a href="#top" className="flex items-center gap-3">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="brand/icon.svg" alt="" width={40} height={40} className="h-10 w-10 rounded-lg" />
              <span className="font-display text-lg font-bold tracking-[0.08em] text-fg">
                CAST<span className="text-forge-400">IRON</span>
              </span>
            </a>
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-iron-text">
              Script to published episode — even when your TTS provider dies. A self-healing
              audio-episode factory forged on Genblaze + Backblaze B2.
            </p>
            <div className="mt-6 flex items-center gap-2.5">
              <a
                href={LINKS.repo}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="GitHub repository"
                className="flex h-9 w-9 items-center justify-center rounded-md border border-iron-strong text-iron-text transition-all duration-200 hover:-translate-y-0.5 hover:border-forge-500/60 hover:text-forge-300"
              >
                <Github className="h-4 w-4" />
              </a>
              <a
                href={LINKS.console}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Live console"
                className="flex h-9 w-9 items-center justify-center rounded-md border border-iron-strong text-iron-text transition-all duration-200 hover:-translate-y-0.5 hover:border-ember-500/60 hover:text-ember-400"
              >
                <Radio className="h-4 w-4" />
              </a>
              <a
                href={LINKS.license}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="MIT License"
                className="flex h-9 w-9 items-center justify-center rounded-md border border-iron-strong text-iron-text transition-all duration-200 hover:-translate-y-0.5 hover:border-iron-strong hover:text-fg"
              >
                <Scale className="h-4 w-4" />
              </a>
            </div>
          </div>

          {/* Link columns */}
          <div className="grid grid-cols-1 gap-10 sm:grid-cols-3">
            {COLUMNS.map((col) => (
              <nav key={col.title} aria-label={col.title}>
                <h3 className="runbook-label">{col.title}</h3>
                <ul className="mt-4 space-y-2.5">
                  {col.links.map((link) => (
                    <li key={link.label}>
                      <a
                        href={link.href}
                        {...(link.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                        className="group inline-flex items-center gap-1.5 text-sm text-iron-text transition-colors duration-200 hover:text-fg"
                      >
                        {link.label}
                        {link.external && (
                          <ArrowUpRight className="h-3 w-3 opacity-0 transition-opacity duration-200 group-hover:opacity-70" />
                        )}
                      </a>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>
        </div>

        <Separator className="my-10" />

        <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-iron-text">
            © 2026 CastIron · MIT licensed · forged for the Backblaze Generative Media Hackathon
          </p>
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-iron-text/70">
            Static page · no cookies · no trackers · 0 dropped episodes
          </p>
        </div>
      </div>
    </footer>
  );
}
