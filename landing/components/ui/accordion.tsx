"use client";

import * as React from "react";
import { Plus } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Hand-rolled, dependency-free accordion with the ShadCN API surface.
 * Accessible (button + aria-expanded + region) and animated via the
 * grid-template-rows 0fr -> 1fr trick, so height animates smoothly.
 */

type AccordionContextValue = {
  open: string | null;
  toggle: (value: string) => void;
};

const AccordionContext = React.createContext<AccordionContextValue | null>(null);
const ItemContext = React.createContext<string>("");

export function Accordion({
  className,
  defaultValue = null,
  children,
}: {
  className?: string;
  defaultValue?: string | null;
  children: React.ReactNode;
}) {
  const [open, setOpen] = React.useState<string | null>(defaultValue);
  const toggle = React.useCallback(
    (value: string) => setOpen((cur) => (cur === value ? null : value)),
    []
  );
  return (
    <AccordionContext.Provider value={{ open, toggle }}>
      <div className={cn("space-y-3", className)}>{children}</div>
    </AccordionContext.Provider>
  );
}

export function AccordionItem({
  value,
  className,
  children,
}: {
  value: string;
  className?: string;
  children: React.ReactNode;
}) {
  const ctx = React.useContext(AccordionContext);
  const isOpen = ctx?.open === value;
  return (
    <ItemContext.Provider value={value}>
      <div
        className={cn(
          "plate rounded-lg transition-colors duration-300",
          isOpen && "border-forge-500/40",
          className
        )}
      >
        {children}
      </div>
    </ItemContext.Provider>
  );
}

export function AccordionTrigger({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  const ctx = React.useContext(AccordionContext);
  const value = React.useContext(ItemContext);
  const isOpen = ctx?.open === value;
  return (
    <button
      type="button"
      aria-expanded={isOpen}
      aria-controls={`accordion-panel-${value}`}
      id={`accordion-trigger-${value}`}
      onClick={() => ctx?.toggle(value)}
      className={cn(
        "group flex w-full items-center justify-between gap-4 px-5 py-4 text-left",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-400 rounded-lg",
        className
      )}
    >
      <span className="font-body text-[15px] font-semibold leading-snug text-fg transition-colors duration-200 group-hover:text-forge-300">
        {children}
      </span>
      <span
        className={cn(
          "grid h-7 w-7 shrink-0 place-items-center rounded-sm border border-iron-strong text-iron-text",
          "transition-all duration-300",
          isOpen
            ? "rotate-45 border-ember-500/60 text-ember-400"
            : "group-hover:border-forge-500/50 group-hover:text-forge-300"
        )}
        aria-hidden="true"
      >
        <Plus className="h-3.5 w-3.5" />
      </span>
    </button>
  );
}

export function AccordionContent({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  const ctx = React.useContext(AccordionContext);
  const value = React.useContext(ItemContext);
  const isOpen = ctx?.open === value;
  return (
    <div
      id={`accordion-panel-${value}`}
      role="region"
      aria-labelledby={`accordion-trigger-${value}`}
      className="grid transition-[grid-template-rows] duration-300 ease-out"
      style={{ gridTemplateRows: isOpen ? "1fr" : "0fr" }}
    >
      <div className="overflow-hidden">
        <div className={cn("px-5 pb-5 text-sm leading-relaxed text-iron-text", className)}>
          {children}
        </div>
      </div>
    </div>
  );
}
