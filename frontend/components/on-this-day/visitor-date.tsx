"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { dateSlug, todayIn, type CalendarDay } from "@/lib/on-this-day";

/**
 * "Today" is worked out on the server in the site's time zone. A visitor whose own date is
 * already different (past midnight there, or not yet) is taken to their own today.
 */
export function VisitorDate({ shown }: { shown: CalendarDay }) {
  const router = useRouter();
  useEffect(() => {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const own = todayIn(zone);
    if (own.month !== shown.month || own.day !== shown.day) {
      router.replace(`/on-this-day/${dateSlug(own)}`);
    }
  }, [router, shown.month, shown.day]);
  return null;
}
