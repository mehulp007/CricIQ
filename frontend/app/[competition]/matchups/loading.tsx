import { Skeleton } from "@/components/ui/skeleton";

export default function MatchupsLoading() {
  return (
    <div
      className="flex flex-col gap-8"
      role="status"
      aria-busy="true"
      aria-label="Loading matchups"
    >
      <div className="flex flex-col gap-3">
        <Skeleton className="h-9 w-64 rounded-lg" />
        <Skeleton className="h-5 w-[32rem] max-w-full rounded" />
      </div>
      <Skeleton className="h-32 rounded-2xl border border-border" />
      <Skeleton className="h-[28rem] rounded-2xl border border-border" />
    </div>
  );
}
