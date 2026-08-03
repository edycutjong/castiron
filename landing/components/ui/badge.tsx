import * as React from "react";
import { cn } from "@/lib/utils";

type Variant = "iron" | "forge" | "ember" | "danger" | "b2";

const variants: Record<Variant, string> = {
  iron: "border-iron-strong bg-coal-850/70 text-iron-text",
  forge: "border-forge-500/40 bg-forge-500/10 text-forge-300",
  ember: "border-ember-500/40 bg-ember-500/10 text-ember-300",
  danger: "border-danger/40 bg-danger/10 text-red-300",
  b2: "border-b2/40 bg-b2/10 text-red-300",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
}

export function Badge({ className, variant = "iron", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-[0.16em]",
        variants[variant],
        className
      )}
      {...props}
    />
  );
}
