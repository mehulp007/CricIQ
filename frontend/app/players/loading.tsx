export default function PlayersLoading() {
  return (
    <div
      className="flex flex-col gap-8"
      role="status"
      aria-busy="true"
      aria-label="Loading players"
    >
      <div className="flex flex-col gap-3">
        <div className="h-9 w-56 animate-pulse rounded-lg bg-muted" />
        <div className="h-5 w-[32rem] max-w-full animate-pulse rounded bg-muted/70" />
      </div>
      <div className="flex flex-wrap gap-2">
        {[288, 160, 144, 224, 160].map((w) => (
          <div key={w} className="h-9 animate-pulse rounded-lg bg-muted" style={{ width: w }} />
        ))}
      </div>
      <div className="h-[36rem] animate-pulse rounded-2xl border border-border bg-card/50" />
    </div>
  );
}
