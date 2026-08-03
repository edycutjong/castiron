import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Canonical outbound links — one source of truth for every CTA. */
export const LINKS = {
  product: "https://castiron.edycu.dev",
  console: "https://api.castiron.edycu.dev/console",
  api: "https://api.castiron.edycu.dev",
  repo: "https://github.com/edycutjong/castiron",
  demoDoc: "https://github.com/edycutjong/castiron/blob/main/DEMO.md",
  readme: "https://github.com/edycutjong/castiron#readme",
  license: "https://github.com/edycutjong/castiron/blob/main/LICENSE",
  issues: "https://github.com/edycutjong/castiron/issues",
  pitch: "https://castiron.edycu.dev/pitch.html",
  devpost: "https://backblaze-generative-media.devpost.com",
  backblaze: "https://www.backblaze.com/cloud-storage",
  releases: "https://github.com/edycutjong/castiron/releases",
} as const;

/** The one-command reproducible proof. */
export const BENCH_CMD = "OFFLINE=1 .venv/bin/python bench.py";
