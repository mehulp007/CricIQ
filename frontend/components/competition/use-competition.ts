"use client";

import { usePathname } from "next/navigation";
import { useSyncExternalStore } from "react";

import {
  COMPETITION_COOKIE,
  competitionOf,
  DEFAULT_COMPETITION,
  isCompetitionId,
  type CompetitionId,
} from "@/lib/competitions";

function readCookie(): CompetitionId {
  const found = document.cookie
    .split("; ")
    .find((part) => part.startsWith(`${COMPETITION_COOKIE}=`))
    ?.split("=")[1];
  return isCompetitionId(found) ? found : DEFAULT_COMPETITION;
}

// The cookie only changes on navigation, which re-renders anyway.
const subscribe = () => () => {};

/** The competition chosen last (the default until the browser has rendered). */
export function useRememberedCompetition(): CompetitionId {
  return useSyncExternalStore(subscribe, readCookie, () => DEFAULT_COMPETITION);
}

/** The competition of the current page; global pages (About, the write-up) use the last one chosen. */
export function useCompetition(): CompetitionId {
  const remembered = useRememberedCompetition();
  return competitionOf(usePathname()) ?? remembered;
}
