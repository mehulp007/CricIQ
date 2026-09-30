import type { ReactNode } from "react";

export function Section({
  id,
  title,
  lede,
  children,
}: {
  id: string;
  title: string;
  lede: string;
  children: ReactNode;
}) {
  return (
    <section
      aria-labelledby={id}
      className="rounded-2xl border border-border bg-card/70 p-5 sm:p-6"
    >
      <h2 id={id} className="text-lg font-semibold tracking-tight">
        {title}
      </h2>
      <p className="mt-1 max-w-3xl text-sm leading-relaxed text-muted-foreground">{lede}</p>
      <div className="mt-5">{children}</div>
    </section>
  );
}

export function Stat({ label, value, context }: { label: string; value: string; context: string }) {
  return (
    <div className="rounded-2xl border border-border bg-card/70 p-5">
      <p className="text-[11px] tracking-wide text-muted-foreground uppercase">{label}</p>
      <p className="mt-2 font-mono text-3xl font-semibold tracking-tight tabular-nums">{value}</p>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{context}</p>
    </div>
  );
}

export function signed(value: number, digits = 3): string {
  return `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(digits)}`;
}
