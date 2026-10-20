"use client";

import { Fragment } from "react";

import { Reveal } from "@/components/ui/stagger-grid";
import { useReveal } from "@/lib/use-reveal";

/**
 * A heading's text that arrives word by word as it comes into view: each word fades in and rises,
 * 60ms after the one before (app/globals.css). The words stay ordinary text with spaces between
 * them, so the heading reads and wraps as before. Anything other than plain text fades in whole.
 *
 * Like every entrance on the site, a heading the visitor already sees as the first page loads
 * stays still, and reduced motion keeps it so.
 */
export function RevealText({ children, className }: { children: React.ReactNode; className?: string }) {
  const { ref, initial } = useReveal<HTMLSpanElement>({ stagger: true });
  if (typeof children !== "string") return <Reveal className={className}>{children}</Reveal>;
  return (
    <span ref={ref} data-stagger="" data-reveal={initial} className={className}>
      {children.split(" ").map((word, i) => (
        <Fragment key={i}>
          {i > 0 && " "}
          <span className="inline-block">{word}</span>
        </Fragment>
      ))}
    </span>
  );
}
