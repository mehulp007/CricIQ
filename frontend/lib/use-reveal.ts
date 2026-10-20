import { useInView } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { prefersReducedMotion, useIsHydrating } from "@/lib/animation";

/**
 * Reveal an element (or, with `stagger`, its children one after another) as it scrolls into view.
 * The element carries `data-reveal`: "hidden" until it arrives, then "in"; app/globals.css does the
 * animating.
 *
 * Nothing the visitor already sees is hidden: content hydrated from the server's HTML waits only
 * if it starts below the fold. Content rendered in the browser (a page reached by a link) starts
 * hidden and enters. Reduced motion shows everything as it is.
 */
export function useReveal<T extends HTMLElement>({ stagger = false }: { stagger?: boolean } = {}) {
  const ref = useRef<T>(null);
  const hydrating = useIsHydrating();
  const [initial] = useState<"hidden" | undefined>(() =>
    !hydrating && !prefersReducedMotion() ? "hidden" : undefined,
  );
  const inView = useInView(ref, { once: true, margin: "0px 0px -80px 0px" });

  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion()) return;
    if (stagger) {
      [...el.children].forEach((child, i) => {
        (child as HTMLElement).style.setProperty("--i", String(i));
      });
    }
    if (el.dataset.reveal === "hidden") return;
    const box = el.getBoundingClientRect();
    if (box.top < window.innerHeight && box.bottom > 0) return;
    el.dataset.reveal = "hidden";
  }, [stagger]);

  useEffect(() => {
    const el = ref.current;
    if (inView && el?.dataset.reveal === "hidden") el.dataset.reveal = "in";
  }, [inView]);

  return { ref, initial };
}
