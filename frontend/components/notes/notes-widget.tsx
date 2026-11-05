"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { NoteCard } from "@/components/notes/note-card";
import { SectionHeader } from "@/components/ui/section-header";
import { Skeleton } from "@/components/ui/skeleton";
import type { NoteSummary } from "@/lib/api/types";
import { getCompetition, type CompetitionId } from "@/lib/competitions";

const COUNT = 3;

/**
 * The latest daily notes (every competition's, or one's). Fetched in the browser, so the
 * page itself stays static; left out when there are none or the API is asleep.
 */
export function NotesWidget({ competition }: { competition?: CompetitionId }) {
  const [notes, setNotes] = useState<NoteSummary[] | null | undefined>(undefined);

  useEffect(() => {
    const query = new URLSearchParams({ limit: String(COUNT) });
    if (competition) query.set("competition", competition);
    let live = true;
    fetch(`/api/notes?${query}`)
      .then((r) => (r.ok ? (r.json() as Promise<{ notes: NoteSummary[] }>) : null))
      .then((found) => live && setNotes(found && found.notes.length > 0 ? found.notes : null))
      .catch(() => live && setNotes(null));
    return () => {
      live = false;
    };
  }, [competition]);

  if (notes === null) return null;
  const label = competition ? getCompetition(competition).label : null;
  return (
    <section aria-labelledby="notes-heading" className="flex flex-col gap-6">
      <SectionHeader
        id="notes-heading"
        title={label ? `Latest from the ${label}` : "Latest notes"}
        description="Written automatically from the ball-by-ball data after every update."
        action={
          <Link
            href={competition ? `/notes?competition=${competition}` : "/notes"}
            className="text-primary underline-offset-4 hover:underline"
          >
            All notes
          </Link>
        }
      />
      <ul className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {(notes ?? Array.from({ length: COUNT }, () => null)).map((note, i) => (
          <li key={note?.date ?? i} className="flex">
            {note ? (
              <NoteCard note={note} className="w-full" />
            ) : (
              <Skeleton className="h-52 w-full rounded-2xl border border-border" />
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
