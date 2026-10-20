import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useInView } from "@/lib/use-in-view";

/** An observer the test fires by hand. */
function stubObserver() {
  const observers: {
    callback: IntersectionObserverCallback;
    options?: IntersectionObserverInit;
  }[] = [];
  const disconnect = vi.fn();
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
        observers.push({ callback, options });
      }
      observe() {}
      disconnect = disconnect;
    },
  );
  const fire = (isIntersecting: boolean) =>
    act(() => {
      const { callback } = observers.at(-1)!;
      callback(
        [{ isIntersecting } as IntersectionObserverEntry],
        {} as unknown as IntersectionObserver,
      );
    });
  return { observers, disconnect, fire };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useInView", () => {
  it("turns true once the element arrives, then stops watching", () => {
    const { observers, disconnect, fire } = stubObserver();
    const ref = { current: document.createElement("div") };
    const { result } = renderHook(() => useInView(ref, "0px 0px -60px 0px"));
    expect(result.current).toBe(false);
    expect(observers[0].options?.rootMargin).toBe("0px 0px -60px 0px");
    fire(false);
    expect(result.current).toBe(false);
    fire(true);
    expect(result.current).toBe(true);
    expect(disconnect).toHaveBeenCalled();
  });
});
