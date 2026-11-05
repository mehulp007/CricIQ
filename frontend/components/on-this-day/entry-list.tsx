"use client";

import { useState } from "react";

import { EntryCard } from "@/components/on-this-day/entry-card";
import { Button } from "@/components/ui/button";
import type { DatedEntry } from "@/lib/on-this-day";

/** How many entries show before "Show more". */
export const FIRST_SHOWN = 12;

/** The day's entries, a dozen at first. */
export function EntryList({ entries }: { entries: DatedEntry[] }) {
  const [all, setAll] = useState(false);
  const shown = all ? entries : entries.slice(0, FIRST_SHOWN);
  return (
    <div className="flex flex-col gap-4">
      <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2" aria-label="Matches on this day">
        {shown.map((entry) => (
          <li key={`${entry.competition}-${entry.match_id}`} className="flex min-w-0">
            <EntryCard entry={entry} />
          </li>
        ))}
      </ul>
      {entries.length > FIRST_SHOWN && (
        <Button variant="outline" size="lg" className="self-start" onClick={() => setAll(!all)}>
          {all ? "Show fewer" : `Show all ${entries.length}`}
        </Button>
      )}
    </div>
  );
}
