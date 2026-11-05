"use client";

import { ApiUnavailable } from "@/components/api-unavailable";

export default function RecordError({ reset }: { error: Error; reset: () => void }) {
  return <ApiUnavailable reset={reset} />;
}
