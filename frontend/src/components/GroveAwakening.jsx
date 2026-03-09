import React, { useState } from "react";
import { ASSETS } from "../data/friendtree.js";
import { LobsterSpirit } from "./LobsterSpirit.jsx";
import { fetchHealth } from "../api.js";

export function GroveAwakening({ stage, lobsterMotions, easterEgg, onLobsterClick, onConnect, savedUrl }) {
  const [url, setUrl] = useState(savedUrl || "http://localhost:18800");
  const [status, setStatus] = useState(null);
  const [checking, setChecking] = useState(false);
  const [ritualOpen, setRitualOpen] = useState(false);

  const handleConnect = async () => {
    setChecking(true);
    setStatus(null);
    try {
      const health = await fetchHealth(url);
      if (health.status === "ok") {
        onConnect(url, health);
      } else {
        setStatus("Server responded but status is not ok.");
      }
    } catch (err) {
      setStatus(`Cannot connect: ${err.message}`);
    } finally {
      setChecking(false);
    }
  };

  const showSpirits = stage !== "EMPTY_GROVE";
  const showRitualSpot = stage === "CONNECTION_RITUAL" && !ritualOpen;
  const showRitualInput = stage === "CONNECTION_RITUAL" && ritualOpen;
  const showWaiting = stage === "WAITING_GROVE";
  const showFirstShadow = stage === "FIRST_SHADOW";

  const lobsterActors = [
    { side: "left", src: ASSETS.characters.lobsterA, name: "Ember", motion: lobsterMotions.left },
    { side: "right", src: ASSETS.characters.lobsterB, name: "Claw", motion: lobsterMotions.right },
  ];

  return (
    <div className="immersive-app">
      <main className={`scene-shell grove-awakening grove-awakening--${stage.toLowerCase().replace(/_/g, "-")}`}>
        <img className="scene-layer scene-layer--bg" src={ASSETS.scene.background} alt="" />
        <div className="grove-fog-overlay grove-fog-overlay--onboarding" aria-hidden="true" />

        {/* Spirits enter with animation */}
        {showSpirits && lobsterActors.map((l) => (
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

        {/* Connection ritual: glowing ground spot */}
        {showRitualSpot && (
          <button
            className="ritual-spot"
            onClick={() => setRitualOpen(true)}
            aria-label="Begin connection"
            type="button"
          >
            <span className="ritual-spot__glow" />
          </button>
        )}

        {/* Connection ritual: input card emerges from ground */}
        {showRitualInput && (
          <div className="ritual-card">
            <div className="ritual-card__inner">
              <img className="ritual-card__seed" src={ASSETS.icons.seed} alt="" />
              <input
                className="ritual-card__input"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleConnect()}
                placeholder="localhost:18800"
                autoFocus
              />
              <button
                className="ritual-card__submit"
                onClick={handleConnect}
                disabled={checking}
                type="button"
                aria-label="Plant seed"
              >
                <img className="ritual-card__submit-art" src={ASSETS.icons.sprout} alt="" />
              </button>
            </div>
            {status && <p className="ritual-card__status">{status}</p>}
          </div>
        )}

        {/* Waiting grove: subtle pulse at center */}
        {showWaiting && (
          <div className="waiting-pulse" aria-hidden="true">
            <span className="waiting-pulse__ring" />
            <span className="waiting-pulse__ring waiting-pulse__ring--delayed" />
          </div>
        )}

        {/* First shadow hint */}
        {showFirstShadow && (
          <div className="first-shadow-hint" aria-hidden="true">
            <span className="first-shadow-hint__glow" />
          </div>
        )}

        <img className="scene-layer scene-layer--front" src={ASSETS.scene.foreground} alt="" />
      </main>
    </div>
  );
}
