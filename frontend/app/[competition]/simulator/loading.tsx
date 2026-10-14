import { Skeleton } from "@/components/ui/skeleton";

export default function SimulatorLoading() {
  return (
    <div
      className="flex flex-col gap-6"
      role="status"
      aria-busy="true"
      aria-label="Loading the simulator"
    >
      <div className="flex flex-col gap-3">
        <Skeleton className="h-9 w-64 rounded-lg" />
        <Skeleton className="h-5 w-[30rem] max-w-full rounded" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-32 rounded-2xl border border-border" />
        ))}
      </div>
      <Skeleton className="h-96 rounded-2xl border border-border" />
    </div>
  );
}
