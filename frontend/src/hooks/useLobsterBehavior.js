import { useEffect, useRef, useState } from "react";

const LOBSTER_EASTER_EGGS = {
  left: [
    "Ember insists this root counts as emotional infrastructure.",
    "Clack-clack. One more topic and this branch gets premium sunlight.",
    "Ember says the petals are decorative, but the curiosity is operational.",
    "This is not pacing. This is strategic root patrol.",
  ],
  right: [
    "Claw heard a rumor that the next bud is trying to look mysterious.",
    "Root meeting minutes: we remain cute and slightly judgmental.",
    "Claw says every good grove needs one beautifully unnecessary detour.",
    "Do not worry. This scuttle is fully research-backed.",
  ],
};

function pickRandomItem(items) {
  if (!items?.length) return "";
  return items[Math.floor(Math.random() * items.length)];
}

export function createLobsterMotion(side) {
  const horizontalRange = side === "left" ? [-28, 18] : [-18, 28];
  const verticalRange = [-12, 8];
  const x = horizontalRange[0] + Math.random() * (horizontalRange[1] - horizontalRange[0]);
  const y = verticalRange[0] + Math.random() * (verticalRange[1] - verticalRange[0]);
  const rotateBase = side === "left" ? -2.5 : 2.5;
  return {
    x: Math.round(x),
    y: Math.round(y),
    rotate: Number((rotateBase + (Math.random() * 7 - 3.5)).toFixed(2)),
    scale: Number((0.97 + Math.random() * 0.12).toFixed(2)),
    durationMs: 1800 + Math.round(Math.random() * 1500),
    pauseMs: 360 + Math.round(Math.random() * 980),
  };
}

export function useLobsterBehavior() {
  const [motions, setMotions] = useState(() => ({
    left: createLobsterMotion("left"),
    right: createLobsterMotion("right"),
  }));
  const [easterEgg, setEasterEgg] = useState(null);

  // Schedule continuous lobster wandering
  useEffect(() => {
    let leftTimer, rightTimer;
    const scheduleSide = (side, delay) => {
      const tick = () => {
        const m = createLobsterMotion(side);
        setMotions((cur) => ({ ...cur, [side]: m }));
        const t = window.setTimeout(tick, m.durationMs + m.pauseMs);
        if (side === "left") leftTimer = t; else rightTimer = t;
      };
      const t = window.setTimeout(tick, delay);
      if (side === "left") leftTimer = t; else rightTimer = t;
    };
    scheduleSide("left", 420);
    scheduleSide("right", 860);
    return () => { window.clearTimeout(leftTimer); window.clearTimeout(rightTimer); };
  }, []);

  // Auto-dismiss easter egg
  useEffect(() => {
    if (!easterEgg) return undefined;
    const t = window.setTimeout(() => setEasterEgg(null), 2600);
    return () => window.clearTimeout(t);
  }, [easterEgg]);

  const handleClick = (side) => {
    setEasterEgg({ side, line: pickRandomItem(LOBSTER_EASTER_EGGS[side]), id: `${side}-${Date.now()}` });
  };

  return { motions, easterEgg, handleClick };
}
