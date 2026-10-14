import { ViewTransition } from "react";

/**
 * Every page enters and leaves with a short fade (globals.css, `.page`). A template remounts on
 * each navigation, so the transition runs between pages while the shell around it stays still.
 * Browsers without view transitions simply switch pages.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <ViewTransition enter="page" exit="page" default="none">
      {children}
    </ViewTransition>
  );
}
