import { Skeleton } from "@/components/ui/skeleton";

export default function PlayerLoading() {
  return (
    <div className="flex flex-col gap-6" role="status" aria-busy="true" aria-label="Loading player">
      <Skeleton className="h-4 w-40 rounded" />
      <div className="flex flex-col gap-3">
        <Skeleton className="h-9 w-72 rounded-lg" />
        <Skeleton className="h-5 w-[28rem] max-w-full rounded" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-32 rounded-2xl border border-border" />
        ))}
      </div>
      <Skeleton className="h-80 rounded-2xl border border-border" />
    </div>
  );
}
