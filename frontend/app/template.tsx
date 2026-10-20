"use client";

import { LazyMotion, MotionConfig, domAnimation, m } from "motion/react";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

// The features load with the page, not lazily: a lazy load re-renders the template while the
// page is still streaming in, and React then renders the unfinished parts again on the client,
// leaving a hidden copy of them behind.

// The first page of a visit appears just as it was rendered (nothing delays its first paint);
// every page after it enters.
const visit = { navigated: false };

/**
 * Pages enter with a spring: they rise 8px into place as they fade in, slowing without a bounce.
 * A template remounts on each navigation, so this runs between pages while the shell around it
 * stays still. With reduced motion pages only fade.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  // The compiler treats module values as constants and would keep the first render's answer to
  // "has the visitor navigated yet?"; this component must read it afresh on every render.
  "use no memo";
  const pathname = usePathname();
  const enter = visit.navigated;
  useEffect(() => {
    visit.navigated = true;
  }, []);
  return (
    <LazyMotion features={domAnimation} strict>
      <MotionConfig reducedMotion="user">
        <m.div
          key={pathname}
          initial={enter ? { opacity: 0, y: 8 } : false}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
        >
          {children}
        </m.div>
      </MotionConfig>
    </LazyMotion>
  );
}
