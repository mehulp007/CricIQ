import { Skeleton } from "@/components/ui/skeleton";

export default function MatchLoading() {
  return (
    <div className="flex flex-col gap-6" role="status" aria-busy="true" aria-label="Loading match">
      <Skeleton className="h-4 w-40 rounded" />
      <Skeleton className="h-9 w-3/4 max-w-xl rounded-lg" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="flex flex-col gap-4 lg:col-span-7">
          <Skeleton className="h-56 rounded-2xl" />
          <Skeleton className="h-72 rounded-2xl" />
        </div>
        <Skeleton className="h-[34rem] rounded-2xl lg:col-span-5" />
      </div>
      <p className="text-sm text-muted-foreground">
        Loading the match. If the analytics engine was asleep this can take up to 30 seconds.
      </p>
    </div>
  );
}
