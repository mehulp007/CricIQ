"use client";

import { ApiUnavailable } from "@/components/api-unavailable";

export default function HeadToHeadError({ reset }: { error: Error; reset: () => void }) {
  return <ApiUnavailable reset={reset} />;
}
