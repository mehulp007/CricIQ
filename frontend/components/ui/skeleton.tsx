import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

/**
 * A loading placeholder with a soft shimmer (still when motion is reduced); give it the size of
 * what it stands in for so nothing shifts when the content arrives.
 */
export function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <div
      aria-hidden="true"
      data-slot="skeleton"
      style={style}
      className={cn("skeleton rounded-xl", className)}
    />
  );
}
