/** Canonical site URL: the Vercel production domain, or localhost in development. */
export const SITE_URL = process.env.VERCEL_PROJECT_PRODUCTION_URL
  ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
  : "http://localhost:3000";

export const SITE_NAME = "CricIQ";
export const SITE_TAGLINE = "Cricket intelligence, ball by ball";
