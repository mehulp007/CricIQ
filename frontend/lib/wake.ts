/**
 * The API runs on a free instance that sleeps when idle and takes up to a minute
 * to wake. Simulator requests made while it wakes fail with 502-504 or a network
 * error; these helpers retry them instead of failing at once.
 */

const WAKING = new Set([502, 503, 504]);
const DELAYS_MS = [2_000, 4_000, 6_000, 8_000, 10_000, 10_000];

/** Start waking the API in the background; safe to call often. */
export function wakeSimulator(): void {
  fetch("/api/warm", { cache: "no-store" }).catch(() => undefined);
}

/**
 * ``fetch`` that retries while the API wakes, calling ``onWaking`` before each
 * retry. Other errors (a 4xx, or a 503 that says the simulator is missing) are
 * returned as they are.
 */
export async function fetchAwake(
  input: string,
  init: RequestInit | undefined,
  onWaking: () => void,
  delays: readonly number[] = DELAYS_MS,
): Promise<Response> {
  for (let attempt = 0; ; attempt += 1) {
    let response: Response | null = null;
    try {
      response = await fetch(input, init);
    } catch {
      // network error: the proxy itself may be cold
    }
    const missing = response?.status === 503 && (await isMissing(response));
    const retry = !response || (WAKING.has(response.status) && !missing);
    if (!retry || attempt >= delays.length) {
      if (response) return response;
      throw new Error("the simulator is unreachable");
    }
    onWaking();
    await new Promise((resolve) => setTimeout(resolve, delays[attempt]));
  }
}

async function isMissing(response: Response): Promise<boolean> {
  try {
    const body = (await response.clone().json()) as { detail?: string };
    return /not available in this build/.test(body.detail ?? "");
  } catch {
    return false;
  }
}
