"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { visit } from "@/lib/animation";

/**
 * Pages enter with a spring: they rise 8px into place as they fade in, slowing without a bounce
 * (`.page-enter` in app/globals.css: CSS keyframes on a spring-shaped curve, so no animation
 * library loads with every page). A template remounts on each navigation, so this runs between
 * pages while the shell around it stays still. The first page of a visit appears just as it was
 * rendered (nothing delays its first paint). With reduced motion pages only fade.
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
    <div key={pathname} className={enter ? "page-enter" : undefined}>
      {children}
    </div>
  );
}
