import { Skeleton } from "@/components/ui/skeleton";

export default function SeriesLoading() {
  return (
    <div className="flex flex-col gap-8" role="status" aria-busy="true" aria-label="Loading series">
      <div className="flex flex-col gap-3">
        <Skeleton className="h-9 w-64 rounded-lg" />
        <Skeleton className="h-5 w-96 max-w-full rounded" />
      </div>
      <div className="flex gap-2">
        {[144, 224, 128].map((w) => (
          <Skeleton key={w} className="h-9 rounded-lg" style={{ width: w }} />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-52 rounded-xl border border-border" />
        ))}
      </div>
    </div>
  );
}
