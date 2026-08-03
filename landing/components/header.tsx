"use client";

import * as React from "react";
import { ArrowUpRight, Github, Menu, X } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn, LINKS } from "@/lib/utils";

const NAV = [
  { href: "#problem", label: "Failure mode" },
  { href: "#drill", label: "Outage drill" },
  { href: "#pillars", label: "Pillars" },
  { href: "#engine", label: "Engine" },
  { href: "#receipts", label: "Receipts" },
  { href: "#faq", label: "FAQ" },
];

export function Header() {
  const [scrolled, setScrolled] = React.useState(false);
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-50 transition-all duration-500",
        scrolled
          ? "border-b border-iron bg-coal-950/85 backdrop-blur-md"
          : "border-b border-transparent bg-transparent"
      )}
    >
      <div className="mx-auto flex h-[4.25rem] max-w-7xl items-center justify-between gap-4 px-5 sm:px-8">
        {/* Element 2: logo, top-left — the animated brand mark itself */}
        <a href="#top" className="group flex items-center gap-3" title="Back to top">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="brand/icon-animated.svg"
            alt=""
            width={36}
            height={36}
            className="h-9 w-9 rounded-lg transition-transform duration-300 group-hover:scale-105"
          />
          <span className="flex flex-col leading-none">
            <span className="font-display text-[15px] font-bold tracking-[0.08em] text-fg">
              CAST<span className="text-forge-400">IRON</span>
            </span>
            <span className="mt-1 font-mono text-[9px] uppercase tracking-widest2 text-iron-text">
              zero dropped episodes
            </span>
          </span>
        </a>

        <nav className="hidden items-center gap-7 lg:flex" aria-label="Primary">
          {NAV.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="font-mono text-[11px] uppercase tracking-[0.18em] text-iron-text transition-colors duration-200 hover:text-ember-400"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2.5">
          <a
            href={LINKS.repo}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="CastIron on GitHub"
            className="hidden h-9 w-9 items-center justify-center rounded-md border border-iron-strong text-iron-text transition-all duration-200 hover:border-forge-500/60 hover:text-forge-300 sm:inline-flex"
          >
            <Github className="h-4 w-4" />
          </a>
          <a
            href={LINKS.console}
            target="_blank"
            rel="noopener noreferrer"
            className={buttonVariants({ variant: "molten", size: "sm", className: "hidden sm:inline-flex" })}
          >
            Open console
            <ArrowUpRight className="h-3.5 w-3.5" />
          </a>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label={open ? "Close menu" : "Open menu"}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-iron-strong text-iron-text transition-colors hover:text-fg lg:hidden"
          >
            {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      <div
        className={cn(
          "grid overflow-hidden border-iron bg-coal-950/95 backdrop-blur-md transition-[grid-template-rows,border-width] duration-300 lg:hidden",
          open ? "border-b" : ""
        )}
        style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
      >
        <div className="min-h-0 overflow-hidden">
          <nav className="flex flex-col gap-1 px-5 py-4" aria-label="Mobile">
            {NAV.map((item) => (
              <a
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className="rounded-md px-3 py-2.5 font-mono text-xs uppercase tracking-[0.18em] text-iron-text transition-colors hover:bg-white/5 hover:text-ember-400"
              >
                {item.label}
              </a>
            ))}
            <a
              href={LINKS.console}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({ variant: "molten", size: "md", className: "mt-3" })}
            >
              Open live console
              <ArrowUpRight className="h-4 w-4" />
            </a>
          </nav>
        </div>
      </div>
    </header>
  );
}
