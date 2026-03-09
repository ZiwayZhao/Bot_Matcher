import React from "react";
import { ASSETS, STATE_META } from "../data/friendtree.js";

function getSummary(branch, viewAs) {
  return viewAs === "user_a" ? branch.summaryA : branch.summaryB;
}

export function BranchStory({ branch, viewAs, onClose, onWater }) {
  if (!branch) return null;
  const meta = STATE_META[branch.state];

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="branch-modal" onClick={(e) => e.stopPropagation()}>
        <div className="branch-modal__header">
          <div>
            <p className="micro-label">Branch Story</p>
            <h2>{branch.topic}</h2>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {onWater ? (
              <button className="glass-button glass-button--accent" onClick={() => onWater(branch)} type="button">
                Water
              </button>
            ) : null}
            <button className="glass-button" onClick={onClose} type="button">Close</button>
          </div>
        </div>
        <div className="branch-modal__state">
          <span className="state-badge" style={{ "--badge-color": meta.color, "--badge-bg": meta.accent }}>
            {meta.label}
          </span>
          <p>{getSummary(branch, viewAs)}</p>
        </div>
        <div className="branch-modal__visual">
          <img src={ASSETS.branches[branch.state]} alt={meta.label} />
        </div>
        {branch.dialogue?.length ? (
          <div className="branch-modal__dialogue">
            <p className="micro-label">Dialogue at this branch</p>
            {branch.dialogue.map((entry, index) => (
              <div className="dialogue-row" key={`${branch.id}-${index}`}>
                <span>{entry.speaker}</span>
                <p>{entry.text}</p>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
