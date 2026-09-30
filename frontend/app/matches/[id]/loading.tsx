export default function MatchLoading() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading match">
      <div className="h-4 w-40 animate-pulse rounded bg-muted/70" />
      <div className="h-9 w-3/4 max-w-xl animate-pulse rounded-lg bg-muted" />
      <div className="grid gap-4 lg:grid-cols-12">
        <div className="flex flex-col gap-4 lg:col-span-7">
          <div className="h-56 animate-pulse rounded-2xl bg-card/60" />
          <div className="h-72 animate-pulse rounded-2xl bg-card/60" />
        </div>
        <div className="h-[34rem] animate-pulse rounded-2xl bg-card/60 lg:col-span-5" />
      </div>
      <p className="text-sm text-muted-foreground">
        Loading the match. If the analytics engine was asleep this can take up to 30 seconds.
      </p>
    </div>
  );
}
