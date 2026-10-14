import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** A section's heading row: title (h2 by default), an optional description and an action. */
export function SectionHeader({
  id,
  title,
  description,
  action,
  as: Heading = "h2",
  className,
}: {
  id?: string;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  as?: "h2" | "h3";
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-x-4 gap-y-2", className)}>
      <div className="flex min-w-0 flex-col gap-1">
        <Heading id={id} className="text-title font-semibold">
          {title}
        </Heading>
        {description && (
          <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">{description}</p>
        )}
      </div>
      {action && <div className="shrink-0 text-sm">{action}</div>}
    </div>
  );
}
