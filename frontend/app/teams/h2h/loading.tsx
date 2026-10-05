export default function HeadToHeadLoading() {
  return (
    <div
      className="flex flex-col gap-6"
      role="status"
      aria-busy="true"
      aria-label="Loading head to head"
    >
      <div className="flex flex-col gap-3">
        <div className="h-9 w-64 animate-pulse rounded-lg bg-muted" />
        <div className="h-5 w-[30rem] max-w-full animate-pulse rounded bg-muted/70" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="h-32 animate-pulse rounded-2xl border border-border bg-card/50" />
        ))}
      </div>
      <div className="h-96 animate-pulse rounded-2xl border border-border bg-card/50" />
    </div>
  );
}
