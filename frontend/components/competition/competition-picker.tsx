"use client";

import { ArrowRight, Trophy } from "lucide-react";
import Link from "next/link";
import { useId, type PointerEvent } from "react";

import { cn } from "@/lib/utils";

export interface PickerCard {
  id: string;
  href: string;
  label: string;
  name: string;
  format: "T20" | "ODI" | "Test";
  /** "2008 to 2026". */
  span: string;
  champion: string | null;
  featured: string | null;
}

// A dot of colour per format (the text stays the foreground colour, for contrast).
const FORMAT_DOT = {
  T20: "bg-primary",
  ODI: "bg-team-a",
  Test: "bg-team-b",
} as const;

const reduceMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Lean the card towards a mouse pointer and move its light there (touch and pens skip this). */
function lean(event: PointerEvent<HTMLAnchorElement>) {
  if (event.pointerType !== "mouse" || reduceMotion()) return;
  const card = event.currentTarget;
  const box = card.getBoundingClientRect();
  const x = (event.clientX - box.left) / box.width;
  const y = (event.clientY - box.top) / box.height;
  card.style.setProperty("--rx", `${((0.5 - y) * 7).toFixed(2)}deg`);
  card.style.setProperty("--ry", `${((x - 0.5) * 9).toFixed(2)}deg`);
  card.style.setProperty("--gx", `${(x * 100).toFixed(1)}%`);
  card.style.setProperty("--gy", `${(y * 100).toFixed(1)}%`);
}

function settle(event: PointerEvent<HTMLAnchorElement>) {
  const card = event.currentTarget;
  for (const name of ["--rx", "--ry", "--gx", "--gy"]) card.style.removeProperty(name);
}

function Card({ card }: { card: PickerCard }) {
  const id = useId();
  return (
    // Named by the competition alone; the rest of the card describes it.
    <Link
      href={card.href}
      aria-label={`${card.label}, ${card.name}`}
      aria-describedby={`${id}-format ${id}-about ${id}-featured`}
      onPointerMove={lean}
      onPointerLeave={settle}
      className="tilt group relative flex h-full flex-col gap-4 rounded-2xl border border-border bg-card p-5 shadow-elev-1 hover:border-primary/40 hover:shadow-elev-3 focus-visible:shadow-elev-3 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <span
        aria-hidden="true"
        className="tilt-light pointer-events-none absolute inset-0 rounded-2xl"
      />
      <span className="tilt-raise flex items-start justify-between gap-3">
        <span className="flex flex-col gap-1">
          <span className="font-mono text-2xl font-semibold tracking-tight">{card.label}</span>
          <span className="font-medium group-hover:text-primary">{card.name}</span>
        </span>
        <span
          id={`${id}-format`}
          className="flex shrink-0 items-center gap-1.5 rounded-full border border-border px-2 py-0.5 font-mono text-[11px] font-medium"
        >
          <span
            className={cn("size-1.5 rounded-full", FORMAT_DOT[card.format])}
            aria-hidden="true"
          />
          {card.format}
        </span>
      </span>
      <span id={`${id}-about`} className="flex flex-col gap-1.5 text-sm text-muted-foreground">
        <span>{card.span}.</span>
        {card.champion && (
          <span className="flex items-center gap-1.5">
            <Trophy className="size-3.5 shrink-0 text-team-b" aria-hidden="true" />
            {card.champion}, the latest champions.
          </span>
        )}
      </span>
      <span className="mt-auto flex items-end justify-between gap-3 border-t border-border pt-3 text-xs text-muted-foreground">
        <span id={`${id}-featured`} className="line-clamp-2">
          {card.featured && <>Featured: {card.featured}</>}
        </span>
        <ArrowRight
          className="size-4 shrink-0 transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
          aria-hidden="true"
        />
      </span>
    </Link>
  );
}

/** The competitions as cards with depth, in groups (leagues, internationals). */
export function CompetitionPicker({
  groups,
}: {
  groups: { title: string; cards: PickerCard[] }[];
}) {
  return (
    <div className="flex flex-col gap-8">
      {groups.map((group) => (
        <div key={group.title} className="flex flex-col gap-3">
          <h3 className="text-sm font-medium text-muted-foreground">{group.title}</h3>
          <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {group.cards.map((card) => (
              <li key={card.id}>
                <Card card={card} />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
