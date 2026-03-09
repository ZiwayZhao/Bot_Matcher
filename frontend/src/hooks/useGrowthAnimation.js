import { useEffect, useRef, useState } from "react";

export const DEFAULT_GROWTH_TIMING = {
  linkDurationMs: 820,
  nodeDelayMs: 520,
  nodeDurationMs: 320,
  cardDelayMs: 760,
  cardDurationMs: 360,
  totalDurationMs: 1320,
};

function usePrefersReducedMotion() {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return undefined;

    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updatePreference = () => {
      setPrefersReducedMotion(mediaQuery.matches);
    };

    updatePreference();
    mediaQuery.addEventListener("change", updatePreference);

    return () => {
      mediaQuery.removeEventListener("change", updatePreference);
    };
  }, []);

  return prefersReducedMotion;
}

export function useGrowthAnimation({ onSettled }) {
  const [growthAnimations, setGrowthAnimations] = useState([]);
  const timerMapRef = useRef(new Map());
  const prefersReducedMotion = usePrefersReducedMotion();

  useEffect(
    () => () => {
      timerMapRef.current.forEach((timer) => window.clearTimeout(timer));
      timerMapRef.current.clear();
    },
    [],
  );

  const startGrowthAnimation = (treeId, branchId) => {
    if (prefersReducedMotion) {
      onSettled(branchId);
      return;
    }

    const animationId = `${treeId}_${branchId}_${Date.now()}`;

    setGrowthAnimations((current) => [
      ...current,
      { id: animationId, treeId, branchId },
    ]);

    const timer = window.setTimeout(() => {
      setGrowthAnimations((current) =>
        current.filter((animation) => animation.id !== animationId),
      );
      timerMapRef.current.delete(animationId);
      onSettled(branchId);
    }, DEFAULT_GROWTH_TIMING.totalDurationMs);

    timerMapRef.current.set(animationId, timer);
  };

  return {
    growthAnimations,
    growthTiming: DEFAULT_GROWTH_TIMING,
    prefersReducedMotion,
    startGrowthAnimation,
  };
}
