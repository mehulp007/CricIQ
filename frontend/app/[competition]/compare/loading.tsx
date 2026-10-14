import { Skeleton } from "@/components/ui/skeleton";

export default function CompareLoading() {
  return (
    <div
      className="flex flex-col gap-8"
      role="status"
      aria-busy="true"
      aria-label="Loading comparison"
    >
      <div className="flex flex-col gap-3">
        <Skeleton className="h-9 w-64 rounded-lg" />
        <Skeleton className="h-5 w-[32rem] max-w-full rounded" />
      </div>
      <Skeleton className="h-32 rounded-2xl border border-border" />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Skeleton className="h-[28rem] rounded-2xl border border-border" />
        <Skeleton className="h-[28rem] rounded-2xl border border-border" />
      </div>
    </div>
  );
}
