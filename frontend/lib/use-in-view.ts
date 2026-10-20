import { useEffect, useState } from "react";

/**
 * Whether an element has come into view, once: true from the moment it first does. `margin` is
 * the observer's root margin (a negative bottom margin waits until it is that far in).
 */
export function useInView(ref: React.RefObject<Element | null>, margin = "0px"): boolean {
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || inView) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        observer.disconnect();
        setInView(true);
      },
      { rootMargin: margin },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref, margin, inView]);
  return inView;
}
