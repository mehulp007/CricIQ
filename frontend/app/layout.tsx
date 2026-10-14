import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Sora } from "next/font/google";

import { AppShell } from "@/components/layout/app-shell";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SITE_NAME, SITE_URL } from "@/lib/site";
import { THEME_SCRIPT } from "@/lib/theme";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Headings. Every font is preloaded: one that arrives after the first paint re-flows the large
// figures and headings (a measured layout shift of 0.12 on the replay).
const sora = Sora({
  variable: "--font-sora",
  subsets: ["latin"],
});

const DESCRIPTION =
  "Cricket analytics for the IPL, men's T20 internationals, ODIs and Tests, BBL, PSL, CPL and SA20, ball by ball: match replay with calibrated win probability and score projection, player profiles against par, and sample-size-aware batter vs bowler matchups.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "CricIQ — Cricket Intelligence, Ball by Ball",
    template: "%s · CricIQ",
  },
  description: DESCRIPTION,
  applicationName: SITE_NAME,
  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    title: "CricIQ — Cricket Intelligence, Ball by Ball",
    description: DESCRIPTION,
  },
  twitter: { card: "summary_large_image" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f8fb" },
    { media: "(prefers-color-scheme: dark)", color: "#0f131b" },
  ],
  colorScheme: "dark light",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // Rendered dark; the <head> script sets the visitor's theme before the first paint, so React
    // must accept the class and style it finds on <html>.
    <html
      lang="en"
      className={`dark ${geistSans.variable} ${geistMono.variable} ${sora.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-full">
        <TooltipProvider delayDuration={200}>
          <AppShell>{children}</AppShell>
        </TooltipProvider>
      </body>
    </html>
  );
}
