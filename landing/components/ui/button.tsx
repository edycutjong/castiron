import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * ShadCN-style button, hand-forged for the Foundry system.
 * `molten` is the primary CTA — an amber ingot with a pulsing heat glow.
 */
type Variant = "molten" | "iron" | "ghost" | "forge";
type Size = "sm" | "md" | "lg" | "xl";

const base =
  "inline-flex items-center justify-center gap-2 font-mono uppercase tracking-[0.14em] " +
  "whitespace-nowrap select-none transition-all duration-300 ease-out " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-400 " +
  "focus-visible:ring-offset-2 focus-visible:ring-offset-coal-950 " +
  "disabled:pointer-events-none disabled:opacity-50";

const variants: Record<Variant, string> = {
  molten:
    "bg-gradient-to-b from-ember-400 to-ember-600 text-coal-950 font-bold " +
    "shadow-[0_0_28px_-6px_rgba(245,158,11,0.55)] " +
    "hover:shadow-[0_0_44px_-4px_rgba(245,158,11,0.75)] hover:brightness-110 hover:-translate-y-0.5 " +
    "active:translate-y-0 active:brightness-95",
  iron:
    "border border-iron-strong bg-coal-850/60 text-fg backdrop-blur " +
    "hover:border-forge-500/60 hover:text-forge-300 hover:-translate-y-0.5 active:translate-y-0",
  ghost: "text-iron-text hover:text-fg hover:bg-white/5",
  forge:
    "bg-gradient-to-b from-forge-400 to-forge-600 text-coal-950 font-bold " +
    "shadow-[0_0_28px_-6px_rgba(16,185,129,0.5)] " +
    "hover:shadow-[0_0_44px_-4px_rgba(16,185,129,0.7)] hover:brightness-110 hover:-translate-y-0.5",
};

const sizes: Record<Size, string> = {
  sm: "h-9 px-4 text-[11px] rounded-md",
  md: "h-11 px-6 text-xs rounded-md",
  lg: "h-13 min-h-[3.25rem] px-8 text-sm rounded-lg",
  xl: "min-h-[3.75rem] px-10 text-base rounded-lg",
};

export function buttonVariants({
  variant = "iron",
  size = "md",
  className,
}: {
  variant?: Variant;
  size?: Size;
  className?: string;
} = {}) {
  return cn(base, variants[variant], sizes[size], className);
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "iron", size = "md", ...props }, ref) => (
    <button ref={ref} className={buttonVariants({ variant, size, className })} {...props} />
  )
);
Button.displayName = "Button";

export { Button };
