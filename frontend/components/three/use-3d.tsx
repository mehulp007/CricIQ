"use client";

import { Component, useEffect, useState, type ReactNode, type RefObject } from "react";

import { can3D, readCapabilities } from "@/lib/three";

/** The events that show a visitor is on the page: any of them lets the 3D start. */
const FIRST_MOVES = ["pointermove", "pointerdown", "touchstart", "wheel", "scroll", "keydown"];

/**
 * Whether 3D may start: after the visitor's first move (pointer, touch, wheel, scroll or key)
 * and once the browser is idle, if `can3D` allows it (WebGL, no reduced motion or saved data, a
 * screen at least `minWidth` wide). Starting three.js takes the main thread for a moment, so the
 * page loads and answers at full speed first.
 */
export function use3DAllowed(minWidth = 0): boolean {
  const [allowed, setAllowed] = useState(false);
  useEffect(() => {
    let idle: number | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const decide = () => setAllowed(can3D(readCapabilities(minWidth)));
    const start = () => {
      stop();
      if ("requestIdleCallback" in window)
        idle = window.requestIdleCallback(decide, { timeout: 1500 });
      else timer = setTimeout(decide, 100);
    };
    const stop = () => {
      for (const name of FIRST_MOVES) window.removeEventListener(name, start);
    };
    for (const name of FIRST_MOVES) window.addEventListener(name, start, { passive: true });
    return () => {
      stop();
      if (idle !== undefined) window.cancelIdleCallback(idle);
      clearTimeout(timer);
    };
  }, [minWidth]);
  return allowed;
}

/** Whether the element is on screen (or within 120 px of it). */
export function useInView(ref: RefObject<HTMLElement | null>): boolean {
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (!("IntersectionObserver" in window)) {
      const id = setTimeout(() => setInView(true), 0);
      return () => clearTimeout(id);
    }
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), {
      rootMargin: "120px",
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref]);
  return inView;
}

/** Whether the tab is visible. */
export function usePageVisible(): boolean {
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const onChange = () => setVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
  }, []);
  return visible;
}

/** A scene that fails (a model that will not load, a lost WebGL context) leaves its fallback. */
export class SceneBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: unknown) {
    console.warn("3D scene unavailable, showing its fallback:", error);
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}
