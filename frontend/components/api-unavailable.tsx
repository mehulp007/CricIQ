"use client";

import { RefreshCw } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

/**
 * Shown when the API cannot be reached. The API runs on a free tier that
 * sleeps when idle, so the usual cause is a cold start; retrying works.
 */
export function ApiUnavailable({ reset }: { reset: () => void }) {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-start gap-4 py-16">
      <p className="font-mono text-sm text-team-b">Engine warming up</p>
      <h1 className="text-2xl font-semibold tracking-tight">The analytics engine is waking up.</h1>
      <p className="leading-relaxed text-muted-foreground">
        CricIQ&apos;s API runs on free hosting that sleeps when nobody is using it. The first
        request after a quiet spell takes about 30 seconds. Try again in a moment. Featured replays
        on the overview page work instantly in the meantime.
      </p>
      <div className="flex flex-wrap gap-3">
        <Button onClick={reset} size="lg">
          <RefreshCw data-icon="inline-start" />
          Try again
        </Button>
        <Button variant="outline" size="lg" asChild>
          <Link href="/">Featured replays</Link>
        </Button>
      </div>
    </div>
  );
}
