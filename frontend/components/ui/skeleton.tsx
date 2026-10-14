import { cn } from "@/lib/utils";

/** A loading placeholder; give it the size of what it stands in for so nothing shifts. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      data-slot="skeleton"
      className={cn("animate-pulse rounded-xl bg-muted/60 motion-reduce:animate-none", className)}
    />
  );
}
