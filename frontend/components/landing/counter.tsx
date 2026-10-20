import type { gsap } from "gsap";

import { cn } from "@/lib/utils";

function format(value: number, decimals: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/**
 * A number that counts up from zero when its chapter arrives, and always ends on the exact value.
 * The page renders the final value (no script, reduced motion and screen readers see only that);
 * `setupCounter` runs the count.
 */
export function Counter({
  value,
  decimals = 0,
  className,
}: {
  value: number;
  decimals?: number;
  className?: string;
}) {
  const text = format(value, decimals);
  return (
    <span className={cn("tabular-nums", className)}>
      <span aria-hidden="true" data-counter={value} data-decimals={decimals}>
        {text}
      </span>
      <span className="sr-only">{text}</span>
    </span>
  );
}

/** Count `el` (a `[data-counter]`) up from zero when `trigger` is pinned in view. */
export function setupCounter(g: typeof gsap, el: HTMLElement, trigger: Element): void {
  const value = Number(el.dataset.counter);
  const decimals = Number(el.dataset.decimals ?? 0);
  if (!Number.isFinite(value)) return;
  const state = { value: 0 };
  el.textContent = format(0, decimals);
  g.to(state, {
    value,
    duration: 2.4,
    ease: "power3.out",
    onUpdate: () => {
      el.textContent = format(state.value, decimals);
    },
    onComplete: () => {
      el.textContent = format(value, decimals);
    },
    scrollTrigger: { trigger, start: "top 40%", once: true },
  });
}
