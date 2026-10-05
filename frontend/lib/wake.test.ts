import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchAwake } from "@/lib/wake";

function reply(status: number, body: unknown = {}) {
  return new Response(JSON.stringify(body), { status });
}

afterEach(() => vi.unstubAllGlobals());

describe("fetchAwake", () => {
  it("retries while the API wakes, then returns its answer", async () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("network"))
      .mockResolvedValueOnce(reply(504))
      .mockResolvedValueOnce(reply(200, { ok: true }));
    vi.stubGlobal("fetch", fetch);
    const onWaking = vi.fn();
    const response = await fetchAwake("/api/x", undefined, onWaking, [0, 0, 0]);
    expect(response.status).toBe(200);
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(onWaking).toHaveBeenCalledTimes(2);
  });

  it("does not retry client errors or a build without the simulator", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(reply(422, { detail: "pick at least 5 bowling options" }))
      .mockResolvedValueOnce(
        reply(503, { detail: "the simulator is not available in this build" }),
      );
    vi.stubGlobal("fetch", fetch);
    expect((await fetchAwake("/api/x", undefined, vi.fn(), [0])).status).toBe(422);
    expect((await fetchAwake("/api/x", undefined, vi.fn(), [0])).status).toBe(503);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("gives up after the last retry", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(502)));
    expect((await fetchAwake("/api/x", undefined, vi.fn(), [0, 0])).status).toBe(502);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network")));
    await expect(fetchAwake("/api/x", undefined, vi.fn(), [0])).rejects.toThrow(/unreachable/);
  });
});
