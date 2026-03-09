import { useMemo } from "react";
import { getTreeStats } from "../data/friendtree.js";

/**
 * Five Seasons of the Grove:
 *   mist          — no connections, solitude
 *   firstLight    — shadow tree appears, curiosity
 *   sprouting     — sprouts growing, discovery
 *   flowering     — resonance/deep, joy
 *   lettingGo     — wilted branches dominate, melancholy
 */

function computeSeason(trees) {
  const treeList = Object.values(trees);
  if (treeList.length === 0) return "mist";

  let totalBranches = 0;
  let sprouts = 0;
  let resonance = 0;
  let deepResonance = 0;
  let wilted = 0;
  let hasShadow = false;

  for (const tree of treeList) {
    if (tree.isShadow) { hasShadow = true; continue; }
    const stats = getTreeStats(tree);
    totalBranches += stats.total;
    sprouts += stats.sprout;
    resonance += stats.resonance;
    deepResonance += stats.deep_resonance;
    wilted += stats.wilted;
  }

  if (totalBranches === 0 && hasShadow) return "firstLight";
  if (totalBranches === 0) return "mist";

  const wiltRatio = wilted / totalBranches;
  if (wiltRatio > 0.5) return "lettingGo";

  const bloomRatio = (resonance + deepResonance) / totalBranches;
  if (bloomRatio >= 0.4 || deepResonance >= 2) return "flowering";

  return "sprouting";
}

const SEASON_VARS = {
  mist: {
    "--grove-fog": 0.72,
    "--grove-saturate": 0.6,
    "--grove-brightness": 0.88,
    "--grove-warmth": 0,
    "--grove-particle-count": 0,
  },
  firstLight: {
    "--grove-fog": 0.48,
    "--grove-saturate": 0.75,
    "--grove-brightness": 0.94,
    "--grove-warmth": 0.15,
    "--grove-particle-count": 2,
  },
  sprouting: {
    "--grove-fog": 0.18,
    "--grove-saturate": 0.92,
    "--grove-brightness": 1.0,
    "--grove-warmth": 0.3,
    "--grove-particle-count": 4,
  },
  flowering: {
    "--grove-fog": 0.04,
    "--grove-saturate": 1.12,
    "--grove-brightness": 1.06,
    "--grove-warmth": 0.6,
    "--grove-particle-count": 8,
  },
  lettingGo: {
    "--grove-fog": 0.32,
    "--grove-saturate": 0.7,
    "--grove-brightness": 0.92,
    "--grove-warmth": 0.45,
    "--grove-particle-count": 6,
  },
};

export function useGroveAtmosphere(trees) {
  return useMemo(() => {
    const season = computeSeason(trees);
    const vars = SEASON_VARS[season];
    return { season, vars };
  }, [trees]);
}
