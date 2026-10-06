/**
 * Responses are cached for a day, keyed by URL. Adding the data version to the
 * URL starts a fresh cache entry as soon as a data sync publishes new data, so
 * pages show it within minutes instead of after the day is up.
 */
export function withVersion(path: string, version: string | null): string {
  if (!version) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}v=${encodeURIComponent(version)}`;
}
