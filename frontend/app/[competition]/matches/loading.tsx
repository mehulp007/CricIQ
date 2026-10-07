export default function MatchesLoading() {
  return (
    <div
      className="flex flex-col gap-8"
      role="status"
      aria-busy="true"
      aria-label="Loading matches"
    >
      <div className="flex flex-col gap-3">
        <div className="h-9 w-64 animate-pulse rounded-lg bg-muted" />
        <div className="h-5 w-96 max-w-full animate-pulse rounded bg-muted/70" />
      </div>
      <div className="flex gap-2">
        {[144, 224, 128].map((w) => (
          <div key={w} className="h-9 animate-pulse rounded-lg bg-muted" style={{ width: w }} />
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="h-52 animate-pulse rounded-xl border border-border bg-card/50" />
        ))}
      </div>
    </div>
  );
}
