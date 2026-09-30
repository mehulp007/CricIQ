import { cn } from "@/lib/utils";

/** Cricket-ball mark: a circle with a curved seam, drawn in the primary accent. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      aria-hidden="true"
      className={cn("size-7 text-primary", className)}
      fill="none"
    >
      <circle cx="16" cy="16" r="13" stroke="currentColor" strokeWidth="2.25" />
      <path
        d="M10.5 5.2c3.2 3 4.9 6.6 4.9 10.8s-1.7 7.8-4.9 10.8M21.5 5.2c-3.2 3-4.9 6.6-4.9 10.8s1.7 7.8 4.9 10.8"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeDasharray="1.6 2.2"
      />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <LogoMark />
      <span className="text-lg font-semibold tracking-tight">
        Cric<span className="text-primary">IQ</span>
      </span>
    </span>
  );
}
