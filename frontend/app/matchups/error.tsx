"use client";

import { ApiUnavailable } from "@/components/api-unavailable";

export default function MatchupsError({ reset }: { error: Error; reset: () => void }) {
  return <ApiUnavailable reset={reset} />;
}
