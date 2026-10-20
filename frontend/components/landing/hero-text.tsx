import type { gsap } from "gsap";
import type { SplitText } from "gsap/SplitText";
import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

/**
 * A chapter headline: the first line bright, the rest muted.
 *
 * The opening headline (`intro`) rises in letter by letter from CSS as the page paints, so the
 * largest text on the page needs no script. Later headlines are split by GSAP SplitText and
 * revealed letter by letter as their chapter arrives (`setupHeroText`). Either way the heading's
 * accessible name is its plain text, and reduced motion shows it at once.
 */
export function HeroText({
  as: Tag = "h2",
  id,
  lines,
  intro = false,
  className,
}: {
  as?: "h1" | "h2";
  id?: string;
  lines: string[];
  intro?: boolean;
  className?: string;
}) {
  const base = cn(
    "font-heading font-semibold tracking-[-0.035em] text-balance text-white",
    className,
  );
  if (!intro) {
    return (
      <Tag id={id} data-split="" className={base}>
        {lines.map((line, i) => (
          <span key={line} className={cn("block", i > 0 && "text-white/55")}>
            {line}
          </span>
        ))}
      </Tag>
    );
  }
  let n = 0;
  return (
    <Tag id={id} aria-label={lines.join(" ")} className={base}>
      {lines.map((line, i) => (
        <span key={line} aria-hidden="true" className={cn("block", i > 0 && "text-white/55")}>
          {line.split(" ").map((word, w) => (
            <span key={w}>
              {w > 0 && " "}
              <span className="inline-block whitespace-nowrap">
                {[...word].map((char, c) => (
                  <span key={c} className="landing-char" style={{ "--i": n++ } as CSSProperties}>
                    {char}
                  </span>
                ))}
              </span>
            </span>
          ))}
        </span>
      ))}
    </Tag>
  );
}

/** Reveal a `[data-split]` headline letter by letter when `trigger` scrolls into view. */
export function setupHeroText(
  g: typeof gsap,
  Split: typeof SplitText,
  el: HTMLElement,
  trigger: Element,
): void {
  Split.create(el, {
    type: "words,chars",
    mask: "words",
    aria: "auto",
    autoSplit: true,
    onSplit: (self) =>
      g.from(self.chars, {
        yPercent: 110,
        opacity: 0,
        duration: 0.8,
        ease: "power3.out",
        stagger: 0.016,
        scrollTrigger: { trigger, start: "top 65%", toggleActions: "play none none reverse" },
      }),
  });
}
