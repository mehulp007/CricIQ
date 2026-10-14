import { Skeleton } from "@/components/ui/skeleton";

export default function PlayersLoading() {
  return (
    <div
      className="flex flex-col gap-8"
      role="status"
      aria-busy="true"
      aria-label="Loading players"
    >
      <div className="flex flex-col gap-3">
        <Skeleton className="h-9 w-56 rounded-lg" />
        <Skeleton className="h-5 w-[32rem] max-w-full rounded" />
      </div>
      <div className="flex flex-wrap gap-2">
        {[288, 160, 144, 224, 160].map((w, i) => (
          <Skeleton key={i} className="h-9 rounded-lg" style={{ width: w }} />
        ))}
      </div>
      <Skeleton className="h-[36rem] rounded-2xl border border-border" />
    </div>
  );
}
