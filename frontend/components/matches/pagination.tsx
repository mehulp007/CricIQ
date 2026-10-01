import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

function pageHref(basePath: string, params: Record<string, string>, page: number): string {
  const next = new URLSearchParams(params);
  if (page <= 1) next.delete("page");
  else next.set("page", String(page));
  const query = next.toString();
  return query ? `${basePath}?${query}` : basePath;
}

const linkClass =
  "inline-flex h-9 items-center gap-1 rounded-lg border border-border px-3 text-sm transition-colors hover:bg-muted";

export function Pagination({
  page,
  pageSize,
  total,
  params,
  basePath = "/matches",
  labels = { previous: "Newer", next: "Older" },
}: {
  page: number;
  pageSize: number;
  total: number;
  params: Record<string, string>;
  basePath?: string;
  labels?: { previous: string; next: string };
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages === 1) return null;
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-4">
      <p className="text-sm text-muted-foreground">
        Page <span className="font-mono text-foreground tabular-nums">{page}</span> of{" "}
        <span className="font-mono tabular-nums">{pages}</span>
      </p>
      <div className="flex gap-2">
        {page > 1 ? (
          <Link href={pageHref(basePath, params, page - 1)} className={linkClass}>
            <ChevronLeft className="size-4" aria-hidden="true" />
            {labels.previous}
          </Link>
        ) : (
          <span className={cn(linkClass, "pointer-events-none opacity-40")}>
            <ChevronLeft className="size-4" aria-hidden="true" />
            {labels.previous}
          </span>
        )}
        {page < pages ? (
          <Link href={pageHref(basePath, params, page + 1)} className={linkClass}>
            {labels.next}
            <ChevronRight className="size-4" aria-hidden="true" />
          </Link>
        ) : (
          <span className={cn(linkClass, "pointer-events-none opacity-40")}>
            {labels.next}
            <ChevronRight className="size-4" aria-hidden="true" />
          </span>
        )}
      </div>
    </nav>
  );
}
