"use client";

import type { Ref } from "react";

import { useReveal } from "@/lib/use-reveal";

/**
 * A grid (or list) whose items enter one after another as it scrolls into view: each fades in and
 * rises 12px, 60ms after the one before. Reduced motion shows them at once.
 */
export function StaggerGrid({
  children,
  className,
  as: Tag = "div",
}: {
  children: React.ReactNode;
  className?: string;
  as?: "div" | "ul" | "ol";
}) {
  const { ref, initial } = useReveal<HTMLElement>({ stagger: true });
  return (
    <Tag
      ref={ref as Ref<never>}
      data-stagger=""
      data-reveal={initial}
      className={className}
    >
      {children}
    </Tag>
  );
}

/** Content that fades in and rises as it scrolls into view (an inline block). */
export function Reveal({ children, className }: { children: React.ReactNode; className?: string }) {
  const { ref, initial } = useReveal<HTMLSpanElement>();
  return (
    <span ref={ref} data-fade="" data-reveal={initial} className={className}>
      {children}
    </span>
  );
}
