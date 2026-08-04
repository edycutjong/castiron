"use client";

import * as React from "react";

/**
 * Shows the current live release (fetched from the GitHub API at runtime) as a
 * "● vX.Y.Z live ↗" chip linking to that release's notes. Static-export safe:
 * renders nothing until the fetch resolves and hides itself on any error, so it
 * never blocks or breaks the page.
 */
const REPO = "edycutjong/castiron";

export function ReleaseBadge() {
  const [rel, setRel] = React.useState<{ tag: string; url: string } | null>(null);

  React.useEffect(() => {
    let alive = true;
    fetch(`https://api.github.com/repos/${REPO}/releases/latest`, {
      headers: { Accept: "application/vnd.github+json" },
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d) => {
        if (alive && d?.tag_name && d?.html_url) setRel({ tag: d.tag_name, url: d.html_url });
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  if (!rel) return null;

  return (
    <a
      href={rel.url}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`Latest release ${rel.tag} on GitHub`}
      className="group inline-flex items-center gap-2 rounded-full border border-iron-strong px-3 py-1 font-mono text-[11px] uppercase tracking-[0.14em] text-iron-text transition-colors duration-200 hover:border-forge-500 hover:text-fg"
    >
      <span className="relative flex h-1.5 w-1.5" aria-hidden="true">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-forge-500 opacity-75" />
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-forge-500" />
      </span>
      {rel.tag} live
      <span aria-hidden="true" className="transition-transform duration-200 group-hover:translate-x-0.5">
        ↗
      </span>
    </a>
  );
}
