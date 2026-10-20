import type { ReactNode } from "react";

import { RevealText } from "@/components/ui/reveal-text";
import { cn } from "@/lib/utils";

/** The top of a page: an optional eyebrow, the page's one h1, a short description and actions. */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  className,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn("flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between", className)}
    >
      <div className="flex min-w-0 flex-col gap-2">
        {eyebrow && (
          <div className="font-mono text-xs tracking-wide text-primary uppercase">{eyebrow}</div>
        )}
        <h1 className="text-headline font-semibold text-balance">
          <RevealText>{title}</RevealText>
        </h1>
        {description && (
          <p className="max-w-3xl text-sm leading-relaxed text-pretty text-muted-foreground sm:text-base">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
