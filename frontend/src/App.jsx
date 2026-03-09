import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ASSETS,
  findBranch,
  getTreeAppearance,
  getTreeStats,
} from "./data/friendtree.js";
import { useGrowthAnimation } from "./hooks/useGrowthAnimation.js";
import { useLobsterBehavior } from "./hooks/useLobsterBehavior.js";
import { useGroveAtmosphere } from "./hooks/useGroveAtmosphere.js";
import { useOnboardingSequence } from "./hooks/useOnboardingSequence.js";
import {
  fetchForest,
  fetchHandshake,
  fetchNotifications,
  acceptConnection,
} from "./api.js";
import { handshakeToTree, formatNotification } from "./data/adapter.js";
import { GroveScene } from "./components/GroveScene.jsx";
import { GroveAwakening } from "./components/GroveAwakening.jsx";
import { BranchStory } from "./components/BranchStory.jsx";

const POLL_INTERVAL_MS = 15000;
const SERVER_KEY = "clawmatch_server_url";

/* ── Notification Toast ── */

function NotificationToast({ notifications, onDismiss, onAction }) {
  if (!notifications?.length) return null;
  const top = notifications[0];
  const formatted = formatNotification(top);
  return (
    <div
      className="soft-card"
      style={{ position: "absolute", top: 22, left: "50%", transform: "translateX(-50%)", zIndex: 12, maxWidth: 420, width: "auto", display: "flex", alignItems: "center", gap: 10, padding: "10px 16px", cursor: "pointer", fontSize: "0.88rem" }}
      onClick={() => onAction?.(top)}
    >
      <img src={formatted.iconArt} alt="" style={{ width: 28, height: 28, objectFit: "contain" }} />
      <p style={{ flex: 1, margin: 0 }}>{top.message}</p>
      <button className="glass-button" onClick={(e) => { e.stopPropagation(); onDismiss(); }} type="button" style={{ padding: "8px 12px", fontSize: "0.82rem" }}>
        ✕
      </button>
      {notifications.length > 1 ? <span style={{ fontSize: "0.78rem", color: "#9d7452" }}>+{notifications.length - 1}</span> : null}
    </div>
  );
}

/* ═══════════════════════════════════════════════
   Main App
   ═══════════════════════════════════════════════ */

export default function App() {
  // Server connection
  const [serverUrl, setServerUrl] = useState(() => localStorage.getItem(SERVER_KEY) || "");
  const [connected, setConnected] = useState(false);
  const [serverInfo, setServerInfo] = useState(null);

  // Tree state
  const [trees, setTrees] = useState({});
  const [activeTreeId, setActiveTreeId] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
  const [selectedBranchId, setSelectedBranchId] = useState(null);
  const [hoveredBranchId, setHoveredBranchId] = useState(null);
  const [highlightedBranchId, setHighlightedBranchId] = useState(null);
  const [statusText, setStatusText] = useState("Waiting for data...");
  const [notifications, setNotifications] = useState([]);
  const dismissedNotifKeys = useRef(new Set());

  // Hooks
  const { motions: lobsterMotions, easterEgg: lobsterEasterEgg, handleClick: handleLobsterClick } = useLobsterBehavior();
  const atmosphere = useGroveAtmosphere(trees);
  const { growthAnimations, growthTiming } = useGrowthAnimation({
    onSettled: (branchId) => setHighlightedBranchId(branchId),
  });

  const treeList = Object.values(trees);
  const hasTrees = treeList.some((t) => !t.isShadow);
  const hasShadowTree = treeList.some((t) => t.isShadow);
  const activeTree = activeTreeId ? trees[activeTreeId] : null;
  const selectedBranch = selectedBranchId && activeTree ? findBranch(activeTree, selectedBranchId) : null;
  const activeStats = useMemo(
    () => activeTree ? getTreeStats(activeTree) : { total: 0, sprout: 0, resonance: 0, deep_resonance: 0, wilted: 0, health: 0 },
    [activeTree],
  );

  const { stage, isOnboarding } = useOnboardingSequence({ connected, hasTrees, hasShadowTree });

  /* ── Server connection ── */

  const handleConnect = useCallback((url, health) => {
    setServerUrl(url);
    setServerInfo(health);
    setConnected(true);
    localStorage.setItem(SERVER_KEY, url);
  }, []);

  const loadForestData = useCallback(async () => {
    if (!serverUrl) return;
    try {
      const [forestRes, notifRes] = await Promise.all([
        fetchForest(serverUrl),
        fetchNotifications(serverUrl).catch(() => ({ notifications: [] })),
      ]);

      const forestTrees = forestRes.trees || [];
      const newTrees = {};

      await Promise.all(
        forestTrees.map(async (entry) => {
          try {
            const handshake = await fetchHandshake(serverUrl, entry.peer_id);
            const tree = handshakeToTree(handshake, entry);
            tree.appearance = getTreeAppearance(tree);
            newTrees[tree.id] = tree;
          } catch { /* skip */ }
        }),
      );

      if (Object.keys(newTrees).length > 0) {
        setTrees(newTrees);
        setActiveTreeId((prev) => (prev && newTrees[prev]) ? prev : Object.keys(newTrees)[0]);
        const total = Object.values(newTrees).reduce((s, t) => s + getTreeStats(t).total, 0);
        setStatusText(`${Object.keys(newTrees).length} trees, ${total} branches total.`);
      } else {
        setStatusText("No trees yet. Connect with other agents to grow your forest.");
      }
      const freshNotifs = (notifRes.notifications || []).filter(
        (n) => !dismissedNotifKeys.current.has(`${n.type}_${n.peer_id}`)
      );
      setNotifications(freshNotifs);
    } catch (err) {
      console.error("Failed to load forest:", err);
    }
  }, [serverUrl]);

  useEffect(() => {
    if (!connected) return undefined;
    loadForestData();
    const interval = setInterval(loadForestData, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [connected, loadForestData]);

  /* ── UI effects ── */

  useEffect(() => {
    if (!highlightedBranchId) return undefined;
    const t = window.setTimeout(() => setHighlightedBranchId(null), 2200);
    return () => window.clearTimeout(t);
  }, [highlightedBranchId]);

  /* ── Actions ── */

  const handleAcceptShadow = async (treeId) => {
    const tree = trees[treeId];
    if (!tree?._peerId) return;
    try {
      await acceptConnection(serverUrl, tree._peerId);
      setStatusText(`Connection with ${tree._peerId} accepted!`);
      loadForestData();
    } catch (err) {
      setStatusText(`Failed to accept: ${err.message}`);
    }
  };

  const handleWater = (branch) => {
    if (!activeTree?._peerId) return;
    setStatusText(`Watering "${branch.topic}"...`);
    setSelectedBranchId(null);
    setTimeout(loadForestData, 1000);
  };

  const handleDismissNotification = () => setNotifications((c) => {
    if (c.length > 0) dismissedNotifKeys.current.add(`${c[0].type}_${c[0].peer_id}`);
    return c.slice(1);
  });

  const handleNotificationAction = (notif) => {
    if (notif.peer_id) {
      const treeId = `tree_${notif.peer_id}`;
      if (trees[treeId]) setActiveTreeId(treeId);
    }
    handleDismissNotification();
  };

  useEffect(() => {
    if (!notifications?.length) return undefined;
    const t = window.setTimeout(handleDismissNotification, 6000);
    return () => window.clearTimeout(t);
  }, [notifications]);

  const handleDisconnect = () => {
    setConnected(false);
    setTrees({});
    setActiveTreeId(null);
    setServerInfo(null);
    localStorage.removeItem(SERVER_KEY);
  };

  /* ── Render ── */

  // Onboarding flow (replaces old ConnectionScreen + waiting screen)
  if (isOnboarding) {
    return (
      <GroveAwakening
        stage={stage}
        lobsterMotions={lobsterMotions}
        easterEgg={lobsterEasterEgg}
        onLobsterClick={handleLobsterClick}
        onConnect={handleConnect}
        savedUrl={serverUrl}
      />
    );
  }

  // Normal grove view — at this point connected=true, activeTree exists
  if (!activeTree) {
    return (
      <div className="immersive-app">
        <main className="scene-shell" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
          <img className="scene-layer scene-layer--bg" src={ASSETS.scene.background} alt="" />
          <div className="brand-card" style={{ position: "relative", zIndex: 5, maxWidth: 420 }}>
            <p className="micro-label">ClawMatch</p>
            <h1>Your Forest</h1>
            <span className="brand-card__meta">Connected to {serverInfo?.peer_id || "server"}. {statusText}</span>
            <button className="glass-button" onClick={loadForestData} type="button">Refresh</button>
            <button className="glass-button" onClick={handleDisconnect} type="button" style={{ marginTop: 8 }}>Disconnect</button>
          </div>
        </main>
      </div>
    );
  }

  const lobsterActors = [
    { side: "left", src: ASSETS.characters.lobsterA, name: "Ember", motion: lobsterMotions.left },
    { side: "right", src: ASSETS.characters.lobsterB, name: "Claw", motion: lobsterMotions.right },
  ];

  return (
    <div className="immersive-app">
      <GroveScene
        tree={activeTree}
        viewAs="user_a"
        selectedId={selectedBranchId}
        highlightedId={highlightedBranchId}
        growthAnimations={growthAnimations}
        growthTiming={growthTiming}
        hoveredId={hoveredBranchId}
        onHover={setHoveredBranchId}
        onLeave={() => setHoveredBranchId(null)}
        onSelect={setSelectedBranchId}
        lobsterActors={lobsterActors}
        easterEgg={lobsterEasterEgg}
        onLobsterClick={handleLobsterClick}
        atmosphere={atmosphere}
      >
        {/* Sidebar */}
        <aside className={["brand-card", "scene-sidebar", sidebarCollapsed && "is-collapsed"].filter(Boolean).join(" ")}>
          <div className="scene-sidebar__header">
            <p className="micro-label">ClawMatch</p>
            <button className="glass-button scene-sidebar__toggle" onClick={() => setSidebarCollapsed((c) => !c)} type="button">
              {sidebarCollapsed ? "Open" : "Hide"}
            </button>
          </div>
          <div className="scene-sidebar__content">
            <div className="scene-sidebar__expanded">
              <h1>{activeTree._peerId || activeTree.label}</h1>
              <div className="brand-card__stats">
                <strong>{activeStats.total} branches</strong>
                {activeTree.matchScore ? <span style={{ fontSize: "0.85rem" }}>Score: {activeTree.matchScore}/10</span> : null}
              </div>
              <div className="brand-card__counts">
                {activeStats.sprout > 0 && <span><img className="state-icon" src={ASSETS.icons.sprout} alt="" /> {activeStats.sprout}</span>}
                {activeStats.resonance > 0 && <span><img className="state-icon" src={ASSETS.icons.resonance} alt="" /> {activeStats.resonance}</span>}
                {activeStats.deep_resonance > 0 && <span><img className="state-icon" src={ASSETS.icons.deep_resonance} alt="" /> {activeStats.deep_resonance}</span>}
                {activeStats.wilted > 0 && <span><img className="state-icon" src={ASSETS.icons.wilted} alt="" /> {activeStats.wilted}</span>}
              </div>
              <div className="brand-card__status"><strong>{statusText}</strong></div>
              {activeTree.isShadow ? (
                <button className="glass-button glass-button--accent" onClick={() => handleAcceptShadow(activeTreeId)} type="button" style={{ width: "100%" }}>
                  Reveal this tree
                </button>
              ) : null}
            </div>
            <button className="scene-sidebar__collapsed-content" onClick={() => setSidebarCollapsed(false)} type="button">
              <span className="scene-sidebar__collapsed-name">{activeTree._peerId || "Tree"}</span>
              <span className="scene-sidebar__collapsed-count">{activeStats.total} branches{activeTree.matchScore ? ` · ${activeTree.matchScore}/10` : ""}</span>
            </button>
          </div>
        </aside>

        {/* Right rail */}
        <aside className="scene-rail">
          <div className="hud-actions scene-rail__actions">
            <button className="glass-button header-action-button" onClick={loadForestData} type="button">Refresh</button>
            <button className="glass-button header-action-button" onClick={handleDisconnect} type="button" style={{ fontSize: "0.78rem" }}>Disconnect</button>
          </div>
          {treeList.length > 1 ? (
            <section className="tree-switcher tree-switcher--rail">
              <p className="micro-label">Forest</p>
              <div className="tree-switcher__stack">
                {treeList.map((tree) => {
                  const stats = getTreeStats(tree);
                  return (
                    <button key={tree.id} className={`switch-pill ${tree.id === activeTreeId ? "is-active" : ""}`} onClick={() => setActiveTreeId(tree.id)} type="button">
                      <strong>{tree._peerId || tree.label}</strong>
                      <span>{stats.total} Branches</span>
                    </button>
                  );
                })}
              </div>
            </section>
          ) : null}
        </aside>

        <NotificationToast notifications={notifications} onDismiss={handleDismissNotification} onAction={handleNotificationAction} />
      </GroveScene>

      <BranchStory branch={selectedBranch} viewAs="user_a" onClose={() => setSelectedBranchId(null)} onWater={activeTree && !activeTree.isShadow ? handleWater : null} />
    </div>
  );
}
