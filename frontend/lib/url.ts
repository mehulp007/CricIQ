/** URL search-param helpers shared by server pages and client filters. */

const ALL = "all";

/** Search params with ``key`` set to ``value`` (removed for "all" or null), back on page 1. */
export function withParam(
  params: URLSearchParams | { toString(): string },
  key: string,
  value: string | null,
): URLSearchParams {
  const next = new URLSearchParams(params.toString());
  if (value === null || value === ALL || value === "") next.delete(key);
  else next.set(key, value);
  if (key !== "page") next.delete("page");
  return next;
}

/** A page's raw search params as URLSearchParams (repeated keys keep their first value). */
export function toSearchParams(
  raw: Record<string, string | string[] | undefined>,
): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(raw)) {
    const first = Array.isArray(value) ? value[0] : value;
    if (first !== undefined) params.set(key, first);
  }
  return params;
}
