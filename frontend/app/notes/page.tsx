import { Rss } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";

import { NoteCard } from "@/components/notes/note-card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { getNotes } from "@/lib/api/client";
import { COMPETITIONS, isCompetitionId } from "@/lib/competitions";
import { parseNoteSlug } from "@/lib/notes";
import { toSearchParams } from "@/lib/url";
import { cn } from "@/lib/utils";

const PAGE = 24;

export const metadata: Metadata = {
  title: "Daily notes",
  description:
    "A short note for every day of men's cricket in the IPL, BBL, PSL, CPL, SA20, T20Is, ODIs and Tests, written automatically from the ball-by-ball data: results, turning points, milestones, records and standings.",
  alternates: { types: { "application/rss+xml": "/notes/feed.xml" } },
};

export default async function NotesPage({ searchParams }: PageProps<"/notes">) {
  await connection();
  const params = toSearchParams(await searchParams);
  const raw = params.get("competition");
  const competition = raw && isCompetitionId(raw) ? raw : undefined;
  const before = parseNoteSlug(params.get("before") ?? "") ?? undefined;
  const list = await getNotes({ limit: PAGE, before, competition });
  const href = (next: { competition?: string; before?: string }) => {
    const query = new URLSearchParams();
    if (next.competition) query.set("competition", next.competition);
    if (next.before) query.set("before", next.before);
    const text = query.toString();
    return `/notes${text ? `?${text}` : ""}`;
  };

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Written from the data"
        title="Daily notes"
        description="What happened on each day of cricket in the data: results, the ball that swung each match, match-winners, milestones, records and standings. Every sentence and figure comes from the ball-by-ball data, by fixed rules."
        actions={
          <a
            href="/notes/feed.xml"
            className="inline-flex items-center gap-1.5 text-sm underline-offset-4 hover:text-primary hover:underline"
          >
            <Rss className="size-4" aria-hidden="true" />
            RSS feed
          </a>
        }
      />
      <nav aria-label="Competition" className="flex flex-wrap gap-1.5">
        {[{ id: undefined, label: "Every competition" }, ...COMPETITIONS].map((c) => {
          const active = c.id === competition;
          return (
            <Link
              key={c.id ?? "all"}
              href={href({ competition: c.id })}
              aria-current={active ? "page" : undefined}
              prefetch={false}
              className={cn(
                "rounded-full border px-3 py-1 text-xs transition-colors",
                active
                  ? "border-primary bg-primary/15 text-foreground"
                  : "border-border text-muted-foreground hover:border-foreground/30 hover:text-foreground",
              )}
            >
              {c.label}
            </Link>
          );
        })}
      </nav>

      {list.notes.length === 0 ? (
        <EmptyState
          title="No notes yet"
          description="Notes are written after each data update; this list fills once the first one is built."
        />
      ) : (
        <>
          <ul className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3" aria-label="Notes">
            {list.notes.map((note) => (
              <li key={note.date} className="flex">
                <NoteCard note={note} className="w-full" level="h2" />
              </li>
            ))}
          </ul>
          <nav aria-label="Older notes" className="flex items-center justify-between gap-3 text-sm">
            {before ? (
              <Link
                href={href({ competition })}
                className="text-primary underline-offset-4 hover:underline"
              >
                Newest notes
              </Link>
            ) : (
              <span />
            )}
            {list.next_before && (
              <Link
                href={href({ competition, before: list.next_before })}
                className="text-primary underline-offset-4 hover:underline"
              >
                Load older notes
              </Link>
            )}
          </nav>
        </>
      )}
      <p className="text-xs text-muted-foreground">{list.method}</p>
    </div>
  );
}
