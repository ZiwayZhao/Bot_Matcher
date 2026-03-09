import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import {
  ASSETS,
  STATE_META,
  TREE_LABEL_LAYOUTS,
  TREE_SKELETONS,
  addBranch,
  cloneTrees,
  findBestGrowthParent,
  findBranch,
  getTreeAppearance,
  getTreeStats,
  nextBranchTopic,
  updateBranch,
} from "./data/friendtree.js";
import { useGrowthAnimation } from "./hooks/useGrowthAnimation.js";
import { ASUKA_TREE_MAP } from "./lib/asukaTreeMap.js";
import { findNextTreeGrowthSlot } from "./lib/treeSlotMap.js";
import {
  fetchForest,
  fetchHandshake,
  fetchHealth,
  fetchNotifications,
  acceptConnection,
} from "./api.js";
import { handshakeToTree, formatNotification } from "./data/adapter.js";

const VIEWBOX = { width: 2816, height: 1536 };
const LABEL_BOX = { width: 396, height: 214 };
const BRANCH_FAMILY_PALETTES = [
  {
    branch: "#6f8f86",
    shadow: "#4f6a63",
    highlight: "#dfe8e2",
    glow: "#aebfb7",
    mist: "#e8efea",
    node: "#f5f6f2",
  },
  {
    branch: "#b38c6c",
    shadow: "#83654c",
    highlight: "#efe3d6",
    glow: "#d3b9a2",
    mist: "#f2ebe3",
    node: "#fbf5ef",
  },
  {
    branch: "#7b8da6",
    shadow: "#56657b",
    highlight: "#e0e6ee",
    glow: "#b4bfcd",
    mist: "#ebeff4",
    node: "#f5f6f8",
  },
  {
    branch: "#a78692",
    shadow: "#7a616a",
    highlight: "#eadfe3",
    glow: "#cdb9c1",
    mist: "#f2eaed",
    node: "#faf5f7",
  },
  {
    branch: "#9087a3",
    shadow: "#685f78",
    highlight: "#e4e0ea",
    glow: "#bdb7c9",
    mist: "#efedf3",
    node: "#f7f5f9",
  },
  {
    branch: "#8d9a79",
    shadow: "#667052",
    highlight: "#e5e8dc",
    glow: "#c0c7b1",
    mist: "#eff1ea",
    node: "#f7f8f2",
  },
];
const STATE_LIGHT_META = {
  sprout: { energy: 0.42, nodeRadius: 32, haloRadius: 56, revealBoost: 0.76 },
  resonance: { energy: 0.62, nodeRadius: 36, haloRadius: 64, revealBoost: 0.96 },
  deep_resonance: { energy: 0.9, nodeRadius: 42, haloRadius: 76, revealBoost: 1.24 },
  difference: { energy: 0.54, nodeRadius: 34, haloRadius: 60, revealBoost: 0.88 },
  wilted: { energy: 0.26, nodeRadius: 30, haloRadius: 52, revealBoost: 0.62 },
};
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

const POLL_INTERVAL_MS = 15000;
const SERVER_KEY = "clawmatch_server_url";

function pickRandomItem(items) {
  if (!items?.length) return "";
  return items[Math.floor(Math.random() * items.length)];
}

function createLobsterMotion(side) {
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

function getSummary(branch, viewAs) {
  return viewAs === "user_a" ? branch.summaryA : branch.summaryB;
}

function clampLabelOffset(node, width, height) {
  const rawX = node.labelDx ?? -width / 2;
  const rawY = node.labelDy ?? -74;
  return {
    x: Math.min(VIEWBOX.width - width - 28 - node.layoutX, Math.max(28 - node.layoutX, rawX)),
    y: Math.min(VIEWBOX.height - height - 32 - node.layoutY, Math.max(28 - node.layoutY, rawY)),
  };
}

function getLabelLayout(treeId, nodeId) {
  return TREE_LABEL_LAYOUTS[treeId]?.[nodeId] || null;
}

function getFallbackSlot(parentNode, childIndex, rootX) {
  const spread = 84 + Math.min(46, childIndex * 14);
  const horizontalDirection = parentNode.layoutX >= rootX ? 1 : -1;
  const verticalRise = 120 + childIndex * 32;
  return {
    points: [
      [parentNode.layoutX, parentNode.layoutY],
      [parentNode.layoutX + horizontalDirection * 64, parentNode.layoutY - Math.max(62, verticalRise * 0.3)],
      [parentNode.layoutX + horizontalDirection * (spread * 0.64), parentNode.layoutY - Math.max(92, verticalRise * 0.72)],
      [parentNode.layoutX + horizontalDirection * (spread + childIndex * 24), parentNode.layoutY - verticalRise],
    ],
    labelDx: horizontalDirection > 0 ? -52 : -72,
    labelDy: -82,
  };
}

function applySkeletonLayout(hierarchy, skeleton) {
  const nodes = hierarchy.descendants();
  const rootNode = nodes.find((node) => node.data.isRoot);
  const [rootX, rootY] = skeleton.root;
  rootNode.layoutX = rootX;
  rootNode.layoutY = rootY;
  nodes.forEach((node) => {
    if (node.data.isRoot) return;
    const childIndex = node.parent.children.indexOf(node);
    const slotKey = `${node.parent.data.id}->${node.data.id}`;
    const slot = skeleton.slots[slotKey] || skeleton.childSlots[node.parent.data.id]?.[childIndex] || getFallbackSlot(node.parent, childIndex, rootX);
    const points = slot.points || [];
    const lastPoint = points[points.length - 1];
    const labelLayout = getLabelLayout(hierarchy.data.id, node.data.id);
    node.pathPoints = points;
    node.layoutX = lastPoint?.[0] ?? rootX;
    node.layoutY = lastPoint?.[1] ?? rootY;
    node.labelDx = labelLayout?.dx ?? -Math.max(160, node.data.topic.length * 30);
    node.labelDy = labelLayout?.dy ?? -84;
  });
  return hierarchy;
}

function applyTreeMapLayout(hierarchy, treeMap) {
  const nodes = hierarchy.descendants();
  const rootNode = nodes.find((node) => node.data.isRoot);
  rootNode.layoutX = treeMap.rootCenter?.x ?? VIEWBOX.width / 2;
  rootNode.layoutY = treeMap.rootCenter?.y ?? VIEWBOX.height - 100;
  rootNode.labelDx = 0;
  rootNode.labelDy = 0;
  nodes.forEach((node) => {
    if (node.data.isRoot) return;
    const slot = treeMap.slots[node.data.slotId];
    const labelLayout = getLabelLayout(hierarchy.data.id, node.data.id);
    if (!slot) {
      node.layoutX = node.parent?.layoutX ?? rootNode.layoutX;
      node.layoutY = node.parent?.layoutY ?? rootNode.layoutY;
      node.pathD = "";
      node.labelDx = labelLayout?.dx;
      node.labelDy = labelLayout?.dy;
      return;
    }
    node.layoutX = slot.dotCenter.x;
    node.layoutY = slot.dotCenter.y;
    node.pathD = slot.pathD;
    node.labelDx = labelLayout?.dx;
    node.labelDy = labelLayout?.dy;
  });
  return hierarchy;
}

function layoutTree(tree) {
  const hierarchy = d3.hierarchy(tree.root, (node) => node.children);
  const skeleton = TREE_SKELETONS[tree.id];

  // Use the shared Figma SVG tree map for all trees (best visuals)
  if (ASUKA_TREE_MAP) {
    return applyTreeMapLayout(hierarchy, ASUKA_TREE_MAP);
  }
  if (skeleton) {
    return applySkeletonLayout(hierarchy, skeleton);
  }

  // Fallback: d3 tree layout
  const treeLayout = d3
    .tree()
    .size([VIEWBOX.width - 760, VIEWBOX.height - 720])
    .separation((a, b) => (a.parent === b.parent ? 1.05 : 1.28));
  treeLayout(hierarchy);
  const nodes = hierarchy.descendants();
  const maxDepth = d3.max(nodes, (node) => node.y) || 1;
  nodes.forEach((node) => {
    node.layoutX = node.x + 420;
    node.layoutY = VIEWBOX.height - 220 - (node.y / maxDepth) * (VIEWBOX.height - 620);
  });
  return hierarchy;
}

function buildLinkPath(link) {
  if (link.target.pathD) return link.target.pathD;
  if (link.target.pathPoints?.length) {
    const line = d3.line().curve(d3.curveCatmullRom.alpha(0.72)).x((p) => p[0]).y((p) => p[1]);
    return line(link.target.pathPoints) || "";
  }
  const sx = link.source.layoutX;
  const sy = link.source.layoutY;
  const tx = link.target.layoutX;
  const ty = link.target.layoutY;
  const trunkLift = link.source.data.isRoot ? 92 : 56;
  return `M ${sx} ${sy} C ${sx} ${sy - trunkLift}, ${tx} ${ty + 44}, ${tx} ${ty}`;
}

function getTopLevelNode(node) {
  const lineage = node.ancestors().slice().reverse();
  return lineage[1] || null;
}

function getBranchPalette(node) {
  const topLevel = getTopLevelNode(node);
  const siblings = topLevel?.parent?.children || [];
  const familyIndex = siblings.findIndex((child) => child.data.id === topLevel?.data.id);
  return BRANCH_FAMILY_PALETTES[(familyIndex === -1 ? 0 : familyIndex) % BRANCH_FAMILY_PALETTES.length];
}

function getBranchVisual(node) {
  return {
    palette: getBranchPalette(node),
    light: STATE_LIGHT_META[node.data.state] || STATE_LIGHT_META.sprout,
    stateMeta: STATE_META[node.data.state],
  };
}

/* ───── Small Components ───── */

function BranchLabelCard({ branch, palette, stateMeta, x, y, selected, growing, growthTiming, onHover, onLeave, onSelect, interactive = true, floating = false }) {
  const Tag = interactive ? "button" : "div";
  const interactiveProps = interactive
    ? { type: "button", onMouseEnter: growing ? undefined : onHover, onMouseLeave: growing ? undefined : onLeave, onClick: growing ? undefined : onSelect }
    : {};

  return (
    <foreignObject x={x} y={y} width={LABEL_BOX.width} height={LABEL_BOX.height} className="branch-label-fo">
      <div xmlns="http://www.w3.org/1999/xhtml" className="branch-label-slot">
        <Tag
          className={["branch-label-card", selected && "branch-label-card--selected", growing && "branch-label-card--growing", floating && "branch-label-card--floating"].filter(Boolean).join(" ")}
          style={{ "--label-accent": palette.branch, "--label-accent-soft": stateMeta.accent, animationDelay: `${growthTiming.cardDelayMs}ms`, animationDuration: `${growthTiming.cardDurationMs}ms` }}
          {...interactiveProps}
        >
          <span className="branch-label-card__accent" />
          <span className="branch-label-card__title">{branch.topic}</span>
          <span className="branch-label-card__state">
            <span className="branch-label-card__emoji">{stateMeta.emoji}</span>
            <span>{stateMeta.tagLabel || stateMeta.label}</span>
          </span>
        </Tag>
      </div>
    </foreignObject>
  );
}

function BranchModal({ branch, viewAs, onClose, onWater }) {
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

function LobsterCharacter({ side, src, name, motion, eggText, onClick }) {
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

function FloatingPanel({ side, title, onClose, children }) {
  return (
    <section className={`floating-panel floating-panel--${side}`}>
      <div className="floating-panel__header">
        <h3>{title}</h3>
        <button className="glass-button floating-panel__close-button" onClick={onClose} type="button">Close</button>
      </div>
      <div className="floating-panel__body">{children}</div>
    </section>
  );
}

/* ───── Connection Screen ───── */

function ConnectionScreen({ onConnect, savedUrl }) {
  const [url, setUrl] = useState(savedUrl || "http://localhost:18800");
  const [status, setStatus] = useState(null);
  const [checking, setChecking] = useState(false);

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

  return (
    <div className="immersive-app">
      <main className="scene-shell" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
        <img className="scene-layer scene-layer--bg" src={ASSETS.scene.background} alt="" />
        <div className="brand-card" style={{ position: "relative", zIndex: 5, maxWidth: 420, width: "100%" }}>
          <p className="micro-label">ClawMatch</p>
          <h1>Connect to Server</h1>
          <span className="brand-card__meta">Enter your bot-matcher server address to see your forest.</span>
          <div className="brand-card__composer" style={{ flexDirection: "column", gap: 10 }}>
            <input value={url} onChange={(e) => setUrl(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleConnect()} placeholder="http://localhost:18800" style={{ width: "100%" }} />
            <button className="glass-button glass-button--accent" onClick={handleConnect} disabled={checking} type="button" style={{ width: "100%" }}>
              {checking ? "Connecting..." : "Connect"}
            </button>
          </div>
          {status ? <div className="brand-card__status"><strong>{status}</strong></div> : null}
        </div>
      </main>
    </div>
  );
}

/* ───── Notification Toast ───── */

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
      <span style={{ fontSize: "1.4rem" }}>{formatted.icon}</span>
      <p style={{ flex: 1, margin: 0 }}>{top.message}</p>
      <button className="glass-button" onClick={(e) => { e.stopPropagation(); onDismiss(); }} type="button" style={{ padding: "8px 12px", fontSize: "0.82rem" }}>
        ✕
      </button>
      {notifications.length > 1 ? <span style={{ fontSize: "0.78rem", color: "#9d7452" }}>+{notifications.length - 1}</span> : null}
    </div>
  );
}

/* ───── Tree Viewport ───── */

function TreeViewport({ tree, viewAs, mistOpacity, selectedId, highlightedId, growthAnimations, growthTiming, hoveredId, onHover, onLeave, onSelect }) {
  const hierarchy = useMemo(() => layoutTree(tree), [tree]);
  const nodes = hierarchy.descendants();
  const links = hierarchy.links();
  const hoveredBranch = hoveredId ? findBranch(tree, hoveredId) : null;
  const exploredNodes = nodes.filter((n) => !n.data.isRoot);
  const activeGrowthAnimations = growthAnimations.filter((a) => a.treeId === tree.id);
  const growingBranchIds = new Set(activeGrowthAnimations.map((a) => a.branchId));

  const rootNode = nodes.find((n) => n.data.isRoot);
  const rootX = rootNode?.layoutX ?? VIEWBOX.width / 2;
  const rootY = rootNode?.layoutY ?? VIEWBOX.height - 100;
  const ambientMistOpacity = Math.max(0.004, mistOpacity * 0.08);
  const sceneGlowOpacity = Math.max(0.2, 1 - ambientMistOpacity * 0.7);
  const isShadow = tree.isShadow;

  return (
    <div className="tree-viewport" style={isShadow ? { filter: "blur(6px) saturate(0.5)", opacity: 0.6 } : undefined}>
      <img className="tree-viewport__art" src={ASSETS.scene.treeFlowersCutout} alt="" />
      <svg className="tree-svg" viewBox={`0 0 ${VIEWBOX.width} ${VIEWBOX.height}`}>
        <defs>
          <filter id="branchGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="10" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <radialGradient id="mistBloom" cx="50%" cy="42%" r="68%">
            <stop offset="0%" stopColor="#fffdf8" stopOpacity="0.98" />
            <stop offset="55%" stopColor="#f6f2ea" stopOpacity="0.92" />
            <stop offset="100%" stopColor="#ede9df" stopOpacity="0.84" />
          </radialGradient>
          <radialGradient id="rootSanctuaryGlow" cx="50%" cy="45%" r="64%">
            <stop offset="0%" stopColor="#fff7ea" stopOpacity="0.92" />
            <stop offset="58%" stopColor="#f0debf" stopOpacity="0.36" />
            <stop offset="100%" stopColor="#dbc5a3" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="rootSanctuaryPool" x1="50%" y1="0%" x2="50%" y2="100%">
            <stop offset="0%" stopColor="#fff8ea" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#e5d1af" stopOpacity="0.2" />
          </linearGradient>
          <mask id="explorationMask" maskUnits="userSpaceOnUse">
            <rect x="0" y="0" width={VIEWBOX.width} height={VIEWBOX.height} fill="white" />
            {links.map((link) => {
              const { light } = getBranchVisual(link.target);
              const w = link.source.data.isRoot ? 28 : 18;
              const path = buildLinkPath(link);
              return (
                <g key={`mist-${link.source.data.id}-${link.target.data.id}`}>
                  <path d={path} fill="none" stroke="black" strokeWidth={w + 80 * light.revealBoost} strokeLinecap="round" opacity={0.16 + light.energy * 0.14} />
                  <path d={path} fill="none" stroke="black" strokeWidth={w + 34 * light.revealBoost} strokeLinecap="round" opacity={0.32 + light.energy * 0.44} />
                </g>
              );
            })}
            {exploredNodes.map((node) => {
              const { light } = getBranchVisual(node);
              return (
                <g key={`mist-node-${node.data.id}`}>
                  <circle cx={node.layoutX} cy={node.layoutY} r={light.haloRadius + 42} fill="black" opacity={0.12 + light.energy * 0.12} />
                  <circle cx={node.layoutX} cy={node.layoutY} r={light.haloRadius + 8} fill="black" opacity={0.3 + light.energy * 0.38} />
                </g>
              );
            })}
            <circle cx={rootX} cy={rootY + 10} r="130" fill="black" opacity="0.34" />
          </mask>
        </defs>

        <g className="tree-mist">
          <rect x="0" y="0" width={VIEWBOX.width} height="940" fill="url(#mistBloom)" opacity={ambientMistOpacity} mask="url(#explorationMask)" />
        </g>

        <g className="tree-lights" pointerEvents="none">
          {links.map((link) => {
            const { palette, light } = getBranchVisual(link.target);
            const path = buildLinkPath(link);
            const w = link.source.data.isRoot ? 28 : 16;
            const isGrowing = growingBranchIds.has(link.target.data.id);
            return <path key={`light-${link.source.data.id}-${link.target.data.id}`} d={path} fill="none" stroke={palette.glow} strokeWidth={w + 18 + light.haloRadius * 0.42} strokeLinecap="round" opacity={isGrowing ? 0 : (0.04 + light.energy * 0.08) * sceneGlowOpacity} filter="url(#branchGlow)" />;
          })}
        </g>

        <g className="tree-links" pointerEvents="none">
          {links.map((link) => {
            const { palette, light } = getBranchVisual(link.target);
            const path = buildLinkPath(link);
            const w = link.source.data.isRoot ? 28 : 16;
            const isGrowing = growingBranchIds.has(link.target.data.id);
            return (
              <g key={`${link.source.data.id}-${link.target.data.id}`}>
                <path d={path} fill="none" stroke={palette.glow} strokeWidth={w + 8} strokeLinecap="round" opacity={isGrowing ? 0 : 0.12 + light.energy * 0.06} filter="url(#branchGlow)" />
                <path d={path} fill="none" stroke={palette.shadow} strokeWidth={w} strokeLinecap="round" opacity={isGrowing ? 0 : 0.9} />
                <path d={path} fill="none" stroke={palette.branch} strokeWidth={Math.max(6, w - 5)} strokeLinecap="round" opacity={isGrowing ? 0 : 0.98} />
                <path d={path} fill="none" stroke={palette.highlight} strokeWidth={Math.max(3.5, w - 10)} strokeLinecap="round" opacity={isGrowing ? 0 : 0.36 + light.energy * 0.22} />
              </g>
            );
          })}
        </g>

        <g className="tree-link-hits">
          {links.map((link) => {
            const branch = link.target.data;
            const path = buildLinkPath(link);
            const w = link.source.data.isRoot ? 50 : 40;
            const growing = growingBranchIds.has(branch.id);
            return <path key={`hit-${link.source.data.id}-${link.target.data.id}`} d={path} fill="none" stroke="transparent" strokeWidth={w} strokeLinecap="round" className={growing ? "branch-link-hit branch-link-hit--growing" : "branch-link-hit"} onMouseEnter={growing ? undefined : () => onHover(branch.id)} onMouseLeave={growing ? undefined : onLeave} onClick={growing ? undefined : () => onSelect(branch.id)} />;
          })}
        </g>

        <g className="tree-growth-effects" pointerEvents="none">
          {activeGrowthAnimations.map((animation) => {
            const link = links.find((item) => item.target.data.id === animation.branchId);
            if (!link) return null;
            const { palette, light } = getBranchVisual(link.target);
            const path = buildLinkPath(link);
            const w = link.source.data.isRoot ? 28 : 16;
            return (
              <g key={animation.id}>
                <path d={path} pathLength="1" className="growth-effect__glow" stroke={palette.glow} strokeWidth={w + 8} style={{ animationDuration: `${growthTiming.linkDurationMs}ms` }} filter="url(#branchGlow)" />
                <path d={path} pathLength="1" className="growth-effect__shadow" stroke={palette.shadow} strokeWidth={w} style={{ animationDuration: `${growthTiming.linkDurationMs}ms` }} />
                <path d={path} pathLength="1" className="growth-effect__stroke" stroke={palette.branch} strokeWidth={Math.max(6, w - 5)} style={{ animationDuration: `${growthTiming.linkDurationMs}ms` }} />
                <path d={path} pathLength="1" className="growth-effect__highlight" stroke={palette.highlight} strokeWidth={Math.max(3.5, w - 10)} style={{ animationDuration: `${growthTiming.linkDurationMs}ms` }} />
                <circle r={light.nodeRadius + 8} fill={palette.glow} opacity="0.72" filter="url(#branchGlow)" className="growth-effect__spark growth-effect__spark--outer">
                  <animateMotion dur={`${growthTiming.linkDurationMs}ms`} path={path} rotate="auto" fill="freeze" />
                </circle>
                <circle r={light.nodeRadius + 2} fill={palette.highlight} opacity="0.96" className="growth-effect__spark">
                  <animateMotion dur={`${growthTiming.linkDurationMs}ms`} path={path} rotate="auto" fill="freeze" />
                </circle>
              </g>
            );
          })}
        </g>

        <g className="tree-root-sanctuary" pointerEvents="none">
          <ellipse cx={rootX} cy={rootY + 18} rx="154" ry="62" fill="url(#rootSanctuaryGlow)" opacity="0.72" />
          <ellipse cx={rootX} cy={rootY + 20} rx="82" ry="24" fill="url(#rootSanctuaryPool)" opacity="0.58" />
        </g>

        <g className="tree-nodes">
          {exploredNodes.map((node) => {
            const branch = node.data;
            const { palette, light, stateMeta } = getBranchVisual(node);
            const growing = growingBranchIds.has(branch.id);
            const selected = selectedId === branch.id;
            const highlighted = highlightedId === branch.id && !growing;
            const haloRadius = light.haloRadius + 18 + (highlighted ? 16 : 0);
            const shellRadius = light.nodeRadius + (selected ? 24 : 20);
            const pearlRadius = light.nodeRadius + 10;
            return (
              <g key={branch.id} transform={`translate(${node.layoutX}, ${node.layoutY})`} className={`branch-hit${growing ? " branch-hit--growing" : ""}`} onMouseEnter={growing ? undefined : () => onHover(branch.id)} onMouseLeave={growing ? undefined : onLeave} onClick={growing ? undefined : () => onSelect(branch.id)}>
                <g className={growing ? "branch-node-shell branch-node-shell--growing" : "branch-node-shell"} style={{ animationDelay: `${growthTiming.nodeDelayMs}ms`, animationDuration: `${growthTiming.nodeDurationMs}ms` }}>
                  <circle className="branch-node-hit-area" r={Math.max(54, haloRadius + 8)} fill="rgba(255,255,255,0.001)" />
                  <circle r={haloRadius} fill={palette.glow} opacity={(highlighted ? 0.34 : 0.16) + light.energy * 0.12} filter="url(#branchGlow)" />
                  <circle r={shellRadius} fill={palette.branch} stroke={palette.highlight} strokeWidth="10" />
                  <circle r={Math.max(24, shellRadius - 8)} fill={palette.node} opacity={0.24} />
                  <circle r={Math.max(22, pearlRadius)} fill={palette.node} opacity={0.94} />
                  <text className="branch-node-emoji" textAnchor="middle" dominantBaseline="central" y="2" style={{ fontSize: `${Math.max(60, light.nodeRadius * 2.2)}px` }}>{stateMeta.emoji}</text>
                </g>
                <text className="branch-node-topic" textAnchor="middle" y={shellRadius + 50} style={{ fontSize: "42px" }}>{branch.topic}</text>
              </g>
            );
          })}
        </g>

        {hoveredBranch ? (() => {
          const hoveredNode = nodes.find((n) => n.data.id === hoveredBranch.id);
          if (!hoveredNode) return null;
          const { palette, stateMeta } = getBranchVisual(hoveredNode);
          const growing = growingBranchIds.has(hoveredBranch.id);
          const selected = selectedId === hoveredBranch.id;
          const labelOffset = clampLabelOffset(hoveredNode, LABEL_BOX.width, LABEL_BOX.height);
          return (
            <g className="tree-hover-card">
              <BranchLabelCard branch={hoveredBranch} palette={palette} stateMeta={stateMeta} x={hoveredNode.layoutX + labelOffset.x} y={hoveredNode.layoutY + labelOffset.y} selected={selected} growing={growing} growthTiming={growthTiming} interactive={false} floating />
            </g>
          );
        })() : null}
      </svg>
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

  // Lobster animations
  const [lobsterMotions, setLobsterMotions] = useState(() => ({
    left: createLobsterMotion("left"),
    right: createLobsterMotion("right"),
  }));
  const [lobsterEasterEgg, setLobsterEasterEgg] = useState(null);

  const activeTree = activeTreeId ? trees[activeTreeId] : null;
  const selectedBranch = selectedBranchId && activeTree ? findBranch(activeTree, selectedBranchId) : null;
  const activeStats = useMemo(
    () => activeTree ? getTreeStats(activeTree) : { total: 0, sprout: 0, resonance: 0, deep_resonance: 0, wilted: 0, health: 0 },
    [activeTree],
  );
  const treeList = Object.values(trees);

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

  useEffect(() => {
    let leftTimer, rightTimer;
    const scheduleSide = (side, delay) => {
      const tick = () => {
        const m = createLobsterMotion(side);
        setLobsterMotions((cur) => ({ ...cur, [side]: m }));
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

  useEffect(() => {
    if (!lobsterEasterEgg) return undefined;
    const t = window.setTimeout(() => setLobsterEasterEgg(null), 2600);
    return () => window.clearTimeout(t);
  }, [lobsterEasterEgg]);

  const { growthAnimations, growthTiming } = useGrowthAnimation({
    onSettled: (branchId) => setHighlightedBranchId(branchId),
  });

  /* ── Actions ── */

  const handleLobsterClick = (side) => {
    setLobsterEasterEgg({ side, line: pickRandomItem(LOBSTER_EASTER_EGGS[side]), id: `${side}-${Date.now()}` });
  };

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

  // Auto-dismiss notifications after 6 seconds
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

  if (!connected) {
    return <ConnectionScreen onConnect={handleConnect} savedUrl={serverUrl} />;
  }

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
      <main className="scene-shell">
        <img className="scene-layer scene-layer--bg" src={ASSETS.scene.background} alt="" />

        {lobsterActors.map((l) => (
          <LobsterCharacter key={l.side} side={l.side} src={l.src} name={l.name} motion={l.motion} eggText={lobsterEasterEgg?.side === l.side ? lobsterEasterEgg.line : null} onClick={() => handleLobsterClick(l.side)} />
        ))}

        <TreeViewport
          tree={activeTree}
          viewAs="user_a"
          mistOpacity={activeTree.appearance?.mistOpacity ?? 0.05}
          selectedId={selectedBranchId}
          highlightedId={highlightedBranchId}
          growthAnimations={growthAnimations}
          growthTiming={growthTiming}
          hoveredId={hoveredBranchId}
          onHover={setHoveredBranchId}
          onLeave={() => setHoveredBranchId(null)}
          onSelect={setSelectedBranchId}
        />

        <img className="scene-layer scene-layer--front" src={ASSETS.scene.foreground} alt="" />

        {/* Sidebar — clean & minimal */}
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
                <strong>🌳 {activeStats.total} branches</strong>
                {activeTree.matchScore ? <span style={{ fontSize: "0.85rem" }}>Score: {activeTree.matchScore}/10</span> : null}
              </div>
              <div className="brand-card__counts">
                {activeStats.sprout > 0 && <span>{activeStats.sprout} 🌱</span>}
                {activeStats.resonance > 0 && <span>{activeStats.resonance} 🤝</span>}
                {activeStats.deep_resonance > 0 && <span>{activeStats.deep_resonance} 🌹</span>}
                {activeStats.wilted > 0 && <span>{activeStats.wilted} 🥀</span>}
              </div>
              <div className="brand-card__status"><strong>{statusText}</strong></div>
              {activeTree.isShadow ? (
                <button className="glass-button glass-button--accent" onClick={() => handleAcceptShadow(activeTreeId)} type="button" style={{ width: "100%" }}>
                  Reveal this tree
                </button>
              ) : null}
            </div>
            <button className="scene-sidebar__collapsed-content" onClick={() => setSidebarCollapsed(false)} type="button">
              <span className="scene-sidebar__collapsed-name">{activeTree.isShadow ? "🌫️ " : ""}{activeTree._peerId || "Tree"}</span>
              <span className="scene-sidebar__collapsed-count">🌳 {activeStats.total}{activeTree.matchScore ? ` · ${activeTree.matchScore}/10` : ""}</span>
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
                      <strong>{tree.isShadow ? "🌫️ " : ""}{tree._peerId || tree.label}</strong>
                      <span>{stats.total} Branches</span>
                    </button>
                  );
                })}
              </div>
            </section>
          ) : null}
        </aside>

        <NotificationToast notifications={notifications} onDismiss={handleDismissNotification} onAction={handleNotificationAction} />
      </main>

      <BranchModal branch={selectedBranch} viewAs="user_a" onClose={() => setSelectedBranchId(null)} onWater={activeTree && !activeTree.isShadow ? handleWater : null} />
    </div>
  );
}
