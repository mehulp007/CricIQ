"use client";

import { useEffect } from "react";

import { COMPETITION_COOKIE, type CompetitionId } from "@/lib/competitions";

const ONE_YEAR = 60 * 60 * 24 * 365;

/** Remembers the competition being browsed, so the home page and global pages lead back to it. */
export function RememberCompetition({ id }: { id: CompetitionId }) {
  useEffect(() => {
    document.cookie = `${COMPETITION_COOKIE}=${id}; path=/; max-age=${ONE_YEAR}; samesite=lax`;
  }, [id]);
  return null;
}
