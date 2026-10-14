import { Skeleton } from "@/components/ui/skeleton";

export default function SeriesDetailLoading() {
  return (
    <div className="flex flex-col gap-8" role="status" aria-busy="true" aria-label="Loading series">
      <Skeleton className="h-4 w-48 rounded" />
      <div className="flex flex-col gap-3">
        <Skeleton className="h-9 w-80 max-w-full rounded-lg" />
        <Skeleton className="h-5 w-96 max-w-full rounded" />
      </div>
      <Skeleton className="h-40 rounded-2xl border border-border" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => (
          <Skeleton key={i} className="h-52 rounded-xl border border-border" />
        ))}
      </div>
    </div>
  );
}
