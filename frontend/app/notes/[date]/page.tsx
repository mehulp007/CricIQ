import { ArrowLeft, ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { NoteInfographic } from "@/components/notes/note-infographic";
import { Badge } from "@/components/ui/badge";
import { ApiError, getNote } from "@/lib/api/client";
import type { Note } from "@/lib/api/types";
import {
  addedLabel,
  articleJsonLd,
  competitionLabel,
  itemsByMatch,
  KIND_LABELS,
  noteDateLabel,
  notePath,
  parseNoteSlug,
} from "@/lib/notes";
import { SITE_URL } from "@/lib/site";

async function load(slug: string): Promise<Note> {
  const date = parseNoteSlug(slug);
  if (!date) notFound();
  try {
    return await getNote(date);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound();
    throw error;
  }
}

export async function generateMetadata({ params }: PageProps<"/notes/[date]">): Promise<Metadata> {
  const date = parseNoteSlug((await params).date);
  if (!date) return {};
  try {
    const note = await getNote(date);
    return {
      title: `${note.headline} · ${noteDateLabel(note.date)}`,
      description: note.summary,
      alternates: { types: { "application/rss+xml": "/notes/feed.xml" } },
    };
  } catch {
    return { title: `Daily notes · ${noteDateLabel(date)}` };
  }
}

export default async function NotePage({ params }: PageProps<"/notes/[date]">) {
  const note = await load((await params).date);
  const groups = itemsByMatch(note.items);
  return (
    <article className="flex flex-col gap-8">
      <script
        type="application/ld+json"
        // The note's own text, escaped for a script element.
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(articleJsonLd(note, SITE_URL)).replace(/</g, "\\u003c"),
        }}
      />
      {/* Notes cover every competition, so the trail is not a competition's. */}
      <Link
        href="/notes"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Daily notes
      </Link>
      <header className="flex flex-col gap-3">
        <p className="font-mono text-xs tracking-wide text-primary uppercase">
          <time dateTime={note.date}>{noteDateLabel(note.date)}</time> ·{" "}
          {note.competitions.map(competitionLabel).join(" · ")}
        </p>
        <h1 className="max-w-4xl text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
          {note.headline}
        </h1>
        <p className="text-sm text-muted-foreground">
          {note.match_count} {note.match_count === 1 ? "match" : "matches"} · Data checked: data
          version {note.data_version}, added {addedLabel(note.added_on)}
        </p>
      </header>

      {note.figures.length > 0 && <NoteInfographic note={note} />}

      <ol className="flex flex-col gap-8" aria-label="The day's matches">
        {groups.map((group) => (
          <li
            key={group.matchId}
            className="flex flex-col gap-4 rounded-2xl border border-border bg-card/70 p-5"
          >
            <ol className="flex flex-col gap-5">
              {group.items.map((item) => (
                <li key={item.position} className="flex gap-3">
                  <span
                    className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/15 font-mono text-xs text-primary"
                    aria-hidden="true"
                  >
                    {item.position}
                  </span>
                  <div className="flex min-w-0 flex-col gap-1.5">
                    <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">{KIND_LABELS[item.kind]}</span>
                      <span>{competitionLabel(item.competition)}</span>
                      {item.model && <Badge variant="outline">Model estimate</Badge>}
                    </p>
                    <h2 className="text-base leading-snug font-semibold text-pretty">
                      {item.title}
                    </h2>
                    {item.body && <p className="text-sm text-muted-foreground">{item.body}</p>}
                    {item.why_it_matters && (
                      <p className="border-l-2 border-primary/50 pl-3 text-sm">
                        <span className="font-medium">Why it matters: </span>
                        {item.why_it_matters}
                      </p>
                    )}
                    {item.links.length > 0 && (
                      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Links">
                        {item.links.map((link) => (
                          <li key={`${link.href}-${link.label}`}>
                            <Link
                              href={link.href}
                              prefetch={false}
                              className="text-primary underline-offset-4 hover:underline"
                            >
                              {link.label}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </li>
        ))}
      </ol>

      <nav aria-label="Other notes" className="flex items-center justify-between gap-3 text-sm">
        {note.previous ? (
          <Link
            href={notePath(note.previous)}
            prefetch={false}
            className="inline-flex items-center gap-1.5 text-primary underline-offset-4 hover:underline"
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            {noteDateLabel(note.previous)}
          </Link>
        ) : (
          <span />
        )}
        {note.next && (
          <Link
            href={notePath(note.next)}
            prefetch={false}
            className="inline-flex items-center gap-1.5 text-primary underline-offset-4 hover:underline"
          >
            {noteDateLabel(note.next)}
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        )}
      </nav>
      <p className="text-xs text-muted-foreground">{note.method}</p>
    </article>
  );
}
