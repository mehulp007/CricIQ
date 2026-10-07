export default function MatchupsLoading() {
  return (
    <div
      className="flex flex-col gap-8"
      role="status"
      aria-busy="true"
      aria-label="Loading matchups"
    >
      <div className="flex flex-col gap-3">
        <div className="h-9 w-64 animate-pulse rounded-lg bg-muted" />
        <div className="h-5 w-[32rem] max-w-full animate-pulse rounded bg-muted/70" />
      </div>
      <div className="h-32 animate-pulse rounded-2xl border border-border bg-card/50" />
      <div className="h-[28rem] animate-pulse rounded-2xl border border-border bg-card/50" />
    </div>
  );
}
