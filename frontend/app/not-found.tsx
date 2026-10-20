import Link from "next/link";

import { Bowled } from "@/components/layout/bowled";

export default function NotFound() {
  return (
    <div className="flex flex-col items-start gap-4 py-16">
      {/* A ball knocks the bails off (the words alone with reduced motion). */}
      <Bowled />
      <p className="font-mono text-sm text-muted-foreground">404 · Out of the ground</p>
      <h1 className="text-3xl font-semibold tracking-tight">This page doesn&apos;t exist.</h1>
      <p className="text-muted-foreground">The link may be wrong, or the page has moved.</p>
      <Link href="/" className="text-primary underline-offset-4 hover:underline">
        Back to the home page
      </Link>
    </div>
  );
}
