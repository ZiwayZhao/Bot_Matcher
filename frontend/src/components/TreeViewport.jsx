import React, { useMemo } from "react";
import * as d3 from "d3";
import {
  ASSETS,
  STATE_META,
  TREE_LABEL_LAYOUTS,
  TREE_SKELETONS,
  findBranch,
} from "../data/friendtree.js";
import { ASUKA_TREE_MAP } from "../lib/asukaTreeMap.js";

export const VIEWBOX = { width: 2816, height: 1536 };
const LABEL_BOX = { width: 396, height: 214 };

export const BRANCH_FAMILY_PALETTES = [
  { branch: "#6f8f86", shadow: "#4f6a63", highlight: "#dfe8e2", glow: "#aebfb7", mist: "#e8efea", node: "#f5f6f2" },
  { branch: "#b38c6c", shadow: "#83654c", highlight: "#efe3d6", glow: "#d3b9a2", mist: "#f2ebe3", node: "#fbf5ef" },
  { branch: "#7b8da6", shadow: "#56657b", highlight: "#e0e6ee", glow: "#b4bfcd", mist: "#ebeff4", node: "#f5f6f8" },
  { branch: "#a78692", shadow: "#7a616a", highlight: "#eadfe3", glow: "#cdb9c1", mist: "#f2eaed", node: "#faf5f7" },
  { branch: "#9087a3", shadow: "#685f78", highlight: "#e4e0ea", glow: "#bdb7c9", mist: "#efedf3", node: "#f7f5f9" },
  { branch: "#8d9a79", shadow: "#667052", highlight: "#e5e8dc", glow: "#c0c7b1", mist: "#eff1ea", node: "#f7f8f2" },
];

export const STATE_LIGHT_META = {
  sprout: { energy: 0.42, nodeRadius: 32, haloRadius: 56, revealBoost: 0.76 },
  resonance: { energy: 0.62, nodeRadius: 36, haloRadius: 64, revealBoost: 0.96 },
  deep_resonance: { energy: 0.9, nodeRadius: 42, haloRadius: 76, revealBoost: 1.24 },
  difference: { energy: 0.54, nodeRadius: 34, haloRadius: 60, revealBoost: 0.88 },
  wilted: { energy: 0.26, nodeRadius: 30, haloRadius: 52, revealBoost: 0.62 },
};

/* ── Layout helpers ── */

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

  if (ASUKA_TREE_MAP) {
    return applyTreeMapLayout(hierarchy, ASUKA_TREE_MAP);
  }
  if (skeleton) {
    return applySkeletonLayout(hierarchy, skeleton);
  }

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

/* ── BranchLabelCard ── */

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
            <img className="branch-label-card__art" src={stateMeta.art} alt="" />
            <span>{stateMeta.tagLabel || stateMeta.label}</span>
          </span>
        </Tag>
      </div>
    </foreignObject>
  );
}

/* ── TreeViewport ── */

export function TreeViewport({ tree, viewAs, mistOpacity, selectedId, highlightedId, growthAnimations, growthTiming, hoveredId, onHover, onLeave, onSelect }) {
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
                  <image href={stateMeta.art} x={-light.nodeRadius * 1.4} y={-light.nodeRadius * 1.4} width={light.nodeRadius * 2.8} height={light.nodeRadius * 2.8} className="branch-node-art" style={{ pointerEvents: "none" }} />
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
