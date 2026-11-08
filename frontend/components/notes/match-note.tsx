import Link from "next/link";

import { Panel } from "@/components/players/profile-parts";
import { Badge } from "@/components/ui/badge";
import type { MatchNote } from "@/lib/api/types";
import { KIND_LABELS, noteDateLabel, notePath } from "@/lib/notes";

/** A match as the daily notes told it: its milestones, records and standings. */
export function MatchNotePanel({ note }: { note: MatchNote }) {
  const items = note.items.filter((i) => i.kind !== "result");
  return (
    <Panel
      id="in-the-notes"
      title="This match in the daily notes"
      lede={
        <>
          From the note for{" "}
          <Link
            href={notePath(note.date)}
            prefetch={false}
            className="text-primary underline-offset-4 hover:underline"
          >
            {noteDateLabel(note.date)}
          </Link>
          , written from the data.
        </>
      }
    >
      {items.length > 0 ? (
        <ul className="flex flex-col gap-3">
          {items.map((item) => (
            <li key={item.position} className="flex flex-col gap-1">
              <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <span className="font-medium text-foreground">{KIND_LABELS[item.kind]}</span>
                {item.model && <Badge variant="outline">Model estimate</Badge>}
              </p>
              <p className="text-sm">{item.title}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">{note.items[0]?.title}</p>
      )}
    </Panel>
  );
}
