import { ArrowRight } from "lucide-react";
import Link from "next/link";

import type { NoteSummary } from "@/lib/api/types";
import { competitionsLabel, noteDateLabel, notePath } from "@/lib/notes";
import { cn } from "@/lib/utils";

/** A note in a list: its date, competitions, headline and the day's main items. */
export function NoteCard({
  note,
  className,
  level = "h3",
}: {
  note: NoteSummary;
  className?: string;
  /** h2 where the cards are the page's sections (the notes list), h3 under a heading. */
  level?: "h2" | "h3";
}) {
  const Heading = level;
  return (
    <Link
      href={notePath(note.date)}
      prefetch={false}
      className={cn(
        "group flex h-full flex-col gap-3 rounded-2xl border border-border bg-card p-5 shadow-elev-1 transition-[border-color,box-shadow] hover:border-primary/40 hover:shadow-elev-2",
        className,
      )}
    >
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <time dateTime={note.date} className="font-medium text-foreground">
          {noteDateLabel(note.date)}
        </time>
        <span>{competitionsLabel(note.competitions)}</span>
        <span>
          {note.match_count} {note.match_count === 1 ? "match" : "matches"}
        </span>
      </p>
      <Heading className="text-base leading-snug font-semibold tracking-tight text-pretty group-hover:text-primary">
        {note.headline}
      </Heading>
      <p className="line-clamp-3 text-sm text-muted-foreground">{note.summary}</p>
      <span className="mt-auto inline-flex items-center gap-1 text-sm text-primary">
        Read the note
        <ArrowRight className="size-4" aria-hidden="true" />
      </span>
    </Link>
  );
}
