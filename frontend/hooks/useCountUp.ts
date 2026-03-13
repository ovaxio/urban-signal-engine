"use client";

import { useState, useEffect, useRef } from "react";

export function useCountUp(target: number, duration = 600): number {
  const [value, setValue] = useState(target);
  const prev = useRef(target);
  const reducedMotion = useRef(false);

  useEffect(() => {
    reducedMotion.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);

  useEffect(() => {
    if (reducedMotion.current) {
      setValue(target);
      prev.current = target;
      return;
    }

    const start = prev.current;
    const delta = target - start;
    if (delta === 0) return;

    const startTime = performance.now();
    let raf: number;

    const tick = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      setValue(Math.round(start + delta * eased));
      if (progress < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        prev.current = target;
      }
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return value;
}
