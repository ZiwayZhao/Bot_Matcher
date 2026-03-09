import React from "react";
import { ASSETS } from "../data/friendtree.js";
import { LobsterSpirit } from "./LobsterSpirit.jsx";
import { TreeViewport } from "./TreeViewport.jsx";

export function GroveScene({
  tree,
  viewAs,
  selectedId,
  highlightedId,
  growthAnimations,
  growthTiming,
  hoveredId,
  onHover,
  onLeave,
  onSelect,
  lobsterActors,
  easterEgg,
  onLobsterClick,
  atmosphere,
  children,
}) {
  return (
    <main className={`scene-shell grove-season--${atmosphere.season}`} style={atmosphere.vars}>
      <img className="scene-layer scene-layer--bg" src={ASSETS.scene.background} alt="" />
      <div className="grove-fog-overlay" aria-hidden="true" />
      <div className="grove-particles" aria-hidden="true" />

      {lobsterActors.map((l) => (
        <LobsterSpirit
          key={l.side}
          side={l.side}
          src={l.src}
          name={l.name}
          motion={l.motion}
          eggText={easterEgg?.side === l.side ? easterEgg.line : null}
          onClick={() => onLobsterClick(l.side)}
        />
      ))}

      <TreeViewport
        tree={tree}
        viewAs={viewAs}
        mistOpacity={tree.appearance?.mistOpacity ?? 0.05}
        selectedId={selectedId}
        highlightedId={highlightedId}
        growthAnimations={growthAnimations}
        growthTiming={growthTiming}
        hoveredId={hoveredId}
        onHover={onHover}
        onLeave={onLeave}
        onSelect={onSelect}
      />

      <img className="scene-layer scene-layer--front" src={ASSETS.scene.foreground} alt="" />

      {children}
    </main>
  );
}
