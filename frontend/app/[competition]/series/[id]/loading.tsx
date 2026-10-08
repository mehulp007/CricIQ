export default function SeriesDetailLoading() {
  return (
    <div className="flex flex-col gap-8" role="status" aria-busy="true" aria-label="Loading series">
      <div className="h-4 w-48 animate-pulse rounded bg-muted/70" />
      <div className="flex flex-col gap-3">
        <div className="h-9 w-80 max-w-full animate-pulse rounded-lg bg-muted" />
        <div className="h-5 w-96 max-w-full animate-pulse rounded bg-muted/70" />
      </div>
      <div className="h-40 animate-pulse rounded-2xl border border-border bg-card/50" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => (
          <div key={i} className="h-52 animate-pulse rounded-xl border border-border bg-card/50" />
        ))}
      </div>
    </div>
  );
}
