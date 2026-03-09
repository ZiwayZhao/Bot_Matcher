import { useCallback, useEffect, useRef, useState } from "react";

const ONBOARDING_KEY = "clawmatch_onboarding";
const SERVER_KEY = "clawmatch_server_url";

/**
 * Onboarding stages:
 *   EMPTY_GROVE       — misty scene, no UI (0-2s)
 *   SPIRITS_ARRIVE    — Ember + Claw slide in (2-4s)
 *   CONNECTION_RITUAL  — glowing spot → click → input rises from ground
 *   WAITING_GROVE     — connected, lobsters wander, waiting for trees
 *   FIRST_SHADOW      — shadow tree fades in, lobsters react
 *   COMPLETE          — transition to normal grove
 */

const STAGES = [
  "EMPTY_GROVE",
  "SPIRITS_ARRIVE",
  "CONNECTION_RITUAL",
  "WAITING_GROVE",
  "FIRST_SHADOW",
  "COMPLETE",
];

export function useOnboardingSequence({ connected, hasTrees, hasShadowTree }) {
  const savedUrl = localStorage.getItem(SERVER_KEY);
  const onboardingDone = localStorage.getItem(ONBOARDING_KEY) === "done";

  // Determine initial stage
  const getInitialStage = () => {
    if (onboardingDone && connected && hasTrees) return "COMPLETE";
    if (onboardingDone && connected) return "WAITING_GROVE";
    if (onboardingDone || savedUrl) return "CONNECTION_RITUAL";
    return "EMPTY_GROVE";
  };

  const [stage, setStage] = useState(getInitialStage);
  const timerRef = useRef(null);

  // Auto-advance timed stages
  useEffect(() => {
    if (stage === "EMPTY_GROVE") {
      timerRef.current = window.setTimeout(() => setStage("SPIRITS_ARRIVE"), 2000);
      return () => window.clearTimeout(timerRef.current);
    }
    if (stage === "SPIRITS_ARRIVE") {
      timerRef.current = window.setTimeout(() => setStage("CONNECTION_RITUAL"), 2200);
      return () => window.clearTimeout(timerRef.current);
    }
    return undefined;
  }, [stage]);

  // Advance when connected
  useEffect(() => {
    if (connected && (stage === "CONNECTION_RITUAL" || stage === "SPIRITS_ARRIVE" || stage === "EMPTY_GROVE")) {
      setStage("WAITING_GROVE");
    }
  }, [connected, stage]);

  // Advance when trees appear
  useEffect(() => {
    if (stage === "WAITING_GROVE" && hasShadowTree) {
      setStage("FIRST_SHADOW");
    } else if (stage === "WAITING_GROVE" && hasTrees) {
      markComplete();
    }
  }, [stage, hasTrees, hasShadowTree]);

  // Advance from first shadow when accepted
  useEffect(() => {
    if (stage === "FIRST_SHADOW" && hasTrees && !hasShadowTree) {
      markComplete();
    }
  }, [stage, hasTrees, hasShadowTree]);

  const markComplete = useCallback(() => {
    localStorage.setItem(ONBOARDING_KEY, "done");
    setStage("COMPLETE");
  }, []);

  const skipToComplete = useCallback(() => {
    localStorage.setItem(ONBOARDING_KEY, "done");
    setStage("COMPLETE");
  }, []);

  const isOnboarding = stage !== "COMPLETE";

  return {
    stage,
    isOnboarding,
    markComplete,
    skipToComplete,
  };
}
