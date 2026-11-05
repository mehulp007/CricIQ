"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { dateSlug, daysIn, MONTHS, type CalendarDay } from "@/lib/on-this-day";
import { cn } from "@/lib/utils";

/** Pick any day of the year: the month, then the day (clamped to the month's length). */
export function DatePicker({ date }: { date: CalendarDay }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const go = (next: CalendarDay) =>
    startTransition(() => router.push(`/on-this-day/${dateSlug(next)}`, { scroll: false }));

  return (
    <div
      role="group"
      aria-label="Choose a date"
      aria-busy={pending}
      className={cn("flex flex-wrap items-center gap-2", pending && "opacity-60")}
    >
      <Select
        value={String(date.month)}
        onValueChange={(m) => {
          const month = Number(m);
          go({ month, day: Math.min(date.day, daysIn(month)) });
        }}
      >
        <SelectTrigger className="w-40" aria-label="Month">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {MONTHS.map((name, i) => (
            <SelectItem key={name} value={String(i + 1)}>
              {name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select
        value={String(date.day)}
        onValueChange={(d) => go({ month: date.month, day: Number(d) })}
      >
        <SelectTrigger className="w-24" aria-label="Day">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {Array.from({ length: daysIn(date.month) }, (_, i) => (
            <SelectItem key={i + 1} value={String(i + 1)}>
              {i + 1}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
