"use client";

import { m } from "motion/react";
import { useState } from "react";

import { useIsHydrating } from "@/lib/animation";

const FROM = {
  below: { y: 28, opacity: 0 },
  left: { x: -48, opacity: 0 },
  right: { x: 48, opacity: 0 },
} as const;

/**
 * Content that springs into place from below, the left or the right as it appears. Give it a
 * `key` that changes with what it shows (a new matchup, a new player), so each new one enters.
 * What the visitor already sees (hydrated from the server's HTML) stays still; reduced motion only
 * fades.
 */
export function SlideIn({
  from = "below",
  delay = 0,
  className,
  children,
}: {
  from?: keyof typeof FROM;
  delay?: number;
  className?: string;
  children: React.ReactNode;
}) {
  const hydrating = useIsHydrating();
  const [initial] = useState(() => (hydrating ? false : FROM[from]));
  return (
    <m.div
      initial={initial}
      animate={{ x: 0, y: 0, opacity: 1 }}
      transition={{ type: "spring", stiffness: 260, damping: 26, delay }}
      className={className}
    >
      {children}
    </m.div>
  );
}
