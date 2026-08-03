"use client";

import * as React from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";

/** Click-to-copy chip for the reproducible bench command. */
export function CopyButton({ text, className }: { text: string; className?: string }) {
  const [copied, setCopied] = React.useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable — no-op */
    }
  };

  return (
    <button
      type="button"
      onClick={copy}
      aria-label={copied ? "Copied" : `Copy command: ${text}`}
      className={cn(
        "group inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-sm border border-iron-strong",
        "text-iron-text transition-all duration-200 hover:border-ember-500/60 hover:text-ember-400",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-400",
        copied && "border-forge-500/60 text-forge-400",
        className
      )}
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}
