"use client";

import { LazyMotion, MotionConfig, domAnimation } from "motion/react";

/**
 * Motion's animation features for the `m` components inside, and its reduced-motion rule (keep
 * only fades). Used around the match replay, the one part of the site that animates with Motion, so
 * no other page loads it. The features load with the component rather than lazily: a lazy load
 * re-renders everything inside once it arrives.
 */
export function MotionProvider({ children }: { children: React.ReactNode }) {
  return (
    <LazyMotion features={domAnimation} strict>
      <MotionConfig reducedMotion="user">{children}</MotionConfig>
    </LazyMotion>
  );
}
