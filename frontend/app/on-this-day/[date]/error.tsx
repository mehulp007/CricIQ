"use client";

import { ApiUnavailable } from "@/components/api-unavailable";

export default function OnThisDateError({ reset }: { error: Error; reset: () => void }) {
  return <ApiUnavailable reset={reset} />;
}
