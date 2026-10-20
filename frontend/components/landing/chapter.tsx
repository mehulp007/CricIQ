import type { ScrollTrigger } from "gsap/ScrollTrigger";

import { cn } from "@/lib/utils";

/** The top bar's height: chapters pin just below it. */
export function topBarHeight(): number {
  return document.querySelector("header")?.getBoundingClientRect().height ?? 56;
}

/**
 * One chapter of the landing story: a full-viewport section (below the top bar) on the shared
 * stage. `setupChapter` pins it for one viewport of scrolling, so the visitor stays on it while its
 * text and the particles play out, then lets it scroll away.
 */
export function Chapter({
  id,
  children,
  className,
}: {
  id: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-heading`}
      data-chapter=""
      className={cn("landing-stage relative z-10 h-(--stage-h) w-full overflow-clip", className)}
    >
      {children}
    </section>
  );
}

/** "01 — The anatomy of a delivery": on the void, or (`tone="app"`) on the app's own background. */
export function ChapterEyebrow({
  number,
  title,
  tone = "void",
}: {
  number: string;
  title: string;
  tone?: "void" | "app";
}) {
  return (
    <p
      className={cn(
        "flex items-center gap-3 font-mono text-[11px] tracking-[0.22em] uppercase",
        tone === "void" ? "text-neon-turf" : "text-primary",
      )}
    >
      <span>{number}</span>
      <span
        aria-hidden="true"
        className={cn("h-px w-8", tone === "void" ? "bg-neon-turf/60" : "bg-primary/60")}
      />
      <span className={tone === "void" ? "text-white/75" : "text-muted-foreground"}>{title}</span>
    </p>
  );
}

/** Pin a chapter for one viewport of scrolling. */
export function setupChapter(Trigger: typeof ScrollTrigger, el: Element) {
  return Trigger.create({
    trigger: el,
    start: () => `top top+=${topBarHeight()}`,
    end: "+=100%",
    pin: true,
    pinSpacing: true,
    anticipatePin: 1,
    invalidateOnRefresh: true,
  });
}
