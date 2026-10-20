"use client";

import { useState } from "react";

import { useIsHydrating } from "@/lib/animation";
import { cn } from "@/lib/utils";

/**
 * Content that springs into place from below, the left or the right as it appears (a CSS keyframe
 * on a spring curve, app/globals.css). Give it a `key` that changes with what it shows (a new
 * matchup, a new player), so each new one enters. What the visitor already sees (hydrated from the
 * server's HTML) stays still; reduced motion only fades. `delay` is in seconds.
 */
export function SlideIn({
  from = "below",
  delay = 0,
  className,
  children,
}: {
  from?: "below" | "left" | "right";
  delay?: number;
  className?: string;
  children: React.ReactNode;
}) {
  const hydrating = useIsHydrating();
  const [enter] = useState(!hydrating);
  return (
    <div
      data-from={from}
      className={cn(enter && "slide-in", className)}
      style={delay ? ({ "--slide-delay": `${delay}s` } as React.CSSProperties) : undefined}
    >
      {children}
    </div>
  );
}
