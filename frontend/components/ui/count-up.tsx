"use client";

import { useLayoutEffect, useRef } from "react";

import { prefersReducedMotion, useIsHydrating } from "@/lib/animation";

const DURATION = 1200;

/**
 * A number that counts up from zero, settling on its exact value, as it scrolls into view.
 *
 * The page renders `text`, the final value as written (so no script, reduced motion and anything
 * reading the page see the real figure). The count runs when the number comes on screen, starting
 * just below it so the reset to zero isn't seen. A number the visitor already sees (hydrated from
 * the server's HTML, on screen) is left as it is; one rendered in the browser counts from the start.
 */
export function CountUp({
  value,
  text,
  className,
}: {
  /** The value as a number (its magnitude is counted; `text` keeps the sign and the format). */
  value: number;
  /** The final text, exactly as the page shows it ("1,243", "+12.3", "54%"). */
  text: string;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const hydrating = useIsHydrating();
  const fromServer = useRef(hydrating);

  useLayoutEffect(() => {
    const el = ref.current;
    const node = el?.firstChild;
    if (!el || !(node instanceof Text) || prefersReducedMotion()) return;
    const [, prefix = "", digits = "", suffix = ""] = /^(\D*)([\d,.]+)(.*)$/.exec(text) ?? [];
    const decimals = digits.split(".")[1]?.length ?? 0;
    const locale = /\d,\d{2},\d{3}/.test(digits) ? "en-IN" : "en-US";
    const format = (v: number) =>
      prefix +
      v.toLocaleString(locale, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
        useGrouping: digits.includes(","),
      }) +
      suffix;

    let frame = 0;
    const run = () => {
      const start = performance.now();
      node.nodeValue = format(0);
      const tick = (now: number) => {
        const t = Math.min((now - start) / DURATION, 1);
        // Fast, then settling into place.
        node.nodeValue = t < 1 ? format(Math.abs(value) * (1 - (1 - t) ** 4)) : text;
        if (t < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    };

    let observer: IntersectionObserver | null = null;
    const box = el.getBoundingClientRect();
    if (box.top < window.innerHeight && box.bottom > 0) {
      if (!fromServer.current) run();
    } else {
      observer = new IntersectionObserver(
        ([entry]) => {
          if (!entry.isIntersecting) return;
          observer?.disconnect();
          run();
        },
        { rootMargin: "0px 0px 120px 0px" },
      );
      observer.observe(el);
    }
    return () => {
      observer?.disconnect();
      cancelAnimationFrame(frame);
      node.nodeValue = text;
    };
  }, [value, text]);

  return (
    <span ref={ref} className={className}>
      {text}
    </span>
  );
}
