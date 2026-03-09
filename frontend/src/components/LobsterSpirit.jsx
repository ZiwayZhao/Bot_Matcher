import React from "react";

export function LobsterSpirit({ side, src, name, motion, eggText, onClick }) {
  return (
    <button
      type="button"
      className={`lobster lobster--${side}`}
      style={{ "--lobster-x": `${motion.x}px`, "--lobster-y": `${motion.y}px`, "--lobster-rotate": `${motion.rotate}deg`, "--lobster-scale": motion.scale, "--lobster-duration": `${motion.durationMs}ms` }}
      onClick={onClick}
      aria-label={`Talk to ${name}`}
    >
      <span className="lobster__shadow" aria-hidden="true" />
      {eggText ? <span className={`lobster__bubble lobster__bubble--${side}`}>{eggText}</span> : null}
      <img src={src} alt="" aria-hidden="true" />
    </button>
  );
}
