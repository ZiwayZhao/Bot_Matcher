/**
 * Adapter: transforms backend handshake JSON into the frontend tree
 * structure expected by App.jsx (friendtree.js format).
 *
 * Backend seedBranch states → frontend branch states:
 *   detected   → sprout
 *   explored   → resonance
 *   resonance  → deep_resonance
 *
 * Backend confidence → used to determine wilted (confidence < 0.2)
 */

const BACKEND_TO_FRONTEND_STATE = {
  detected: "sprout",
  explored: "resonance",
  resonance: "deep_resonance",
};

function mapState(backendState, confidence) {
  if (confidence != null && confidence < 0.2) return "wilted";
  return BACKEND_TO_FRONTEND_STATE[backendState] || "sprout";
}

function mapDialogue(dialogueSeed) {
  if (!dialogueSeed?.length) return [];
  return dialogueSeed.map((entry) => ({
    speaker: entry.speaker || "Claw",
    text: entry.text || "",
  }));
}

/**
 * Build a hierarchical tree from flat seedBranches.
 *
 * seedBranches have `parentSeedId` to indicate parent-child relationships.
 * Top-level branches (parentSeedId === null) hang off the root.
 */
function buildBranchHierarchy(seedBranches) {
  const byId = new Map();
  const topLevel = [];

  // First pass: create branch objects
  seedBranches.forEach((seed, index) => {
    const branch = {
      id: seed.seedId || `seed_${index}`,
      slotId: String(index + 1),
      topic: seed.topic || "Unknown",
      state: mapState(seed.state, seed.confidence),
      summaryA: seed.summaryA || "",
      summaryB: seed.summaryB || "",
      dialogue: mapDialogue(seed.dialogueSeed),
      children: [],
      // Extra fields for watering UI
      _confidence: seed.confidence,
      _matchDimension: seed.matchDimension,
      _memoryTier: seed.memoryTierUsed,
    };
    byId.set(branch.id, branch);
  });

  // Second pass: build hierarchy
  seedBranches.forEach((seed, index) => {
    const branch = byId.get(seed.seedId || `seed_${index}`);
    if (seed.parentSeedId && byId.has(seed.parentSeedId)) {
      const parent = byId.get(seed.parentSeedId);
      parent.children.push(branch);
      // Update child slotId to be "parentSlot-childIndex"
      const childIndex = parent.children.length;
      branch.slotId = `${parent.slotId}-${childIndex}`;
    } else {
      topLevel.push(branch);
    }
  });

  return topLevel;
}

/**
 * Convert a backend handshake JSON to a frontend tree object.
 *
 * @param {object} handshake — full handshake JSON from GET /handshake?peer=X
 * @param {object} forestEntry — the tree summary from GET /forest
 * @returns {object} — tree compatible with friendtree.js format
 */
export function handshakeToTree(handshake, forestEntry = {}) {
  const peerId = handshake.userBId || forestEntry.peer_id || "unknown";
  const ownId = handshake.userAId || "self";
  const visibility = handshake.visibility || {};
  const isShadow = visibility.sideB === "shadow";

  const seedBranches = handshake.bootstrap?.seedBranches || [];
  const topLevelBranches = buildBranchHierarchy(seedBranches);

  const tree = {
    id: `tree_${peerId}`,
    label: `${ownId} × ${peerId}`,
    subtitle: isShadow
      ? "A mysterious tree growing in the shadows..."
      : `Your friendship tree with ${peerId}`,
    partnerId: peerId,
    isShadow,
    visibility,
    matchScore: handshake.matchSummary?.score || forestEntry.match_score || 0,
    stage: handshake.stage || forestEntry.stage || "initial",
    sceneStatus: isShadow
      ? "This tree is still hidden in shadow. Accept the connection to reveal it."
      : `This tree has ${topLevelBranches.length} main branches growing.`,
    root: {
      id: "root",
      topic: "FriendTree",
      isRoot: true,
      children: topLevelBranches,
    },
    // Keep handshake reference for watering
    _handshakeId: handshake.handshakeId,
    _peerId: peerId,
    _createdAt: handshake.createdAt || forestEntry.createdAt,
    _lastWateredAt: forestEntry.lastWateredAt,
  };

  return tree;
}

/**
 * Create a minimal tree entry for a shadow connection
 * (when we only have forest data, no handshake yet).
 */
export function shadowConnectionToTree(connection) {
  return {
    id: `tree_${connection.peer_id}`,
    label: `? × ${connection.peer_id}`,
    subtitle: "A mysterious tree appeared...",
    partnerId: connection.peer_id,
    isShadow: true,
    visibility: { sideA: "shadow", sideB: "shadow" },
    matchScore: connection.match_score || 0,
    stage: "shadow",
    sceneStatus: "Accept this connection to see what grows.",
    root: {
      id: "root",
      topic: "FriendTree",
      isRoot: true,
      children: [],
    },
    _peerId: connection.peer_id,
    _connectionStatus: connection.status || "pending",
  };
}

/**
 * Map notification types to user-friendly messages.
 */
export function formatNotification(notification) {
  const iconArts = {
    wilt_warning: "/assets/icons/icon_wilted.svg",
    new_tree: "/assets/icons/icon_sprout.svg",
    shadow_tree: "/assets/icons/icon_seed.svg",
    resonance_opportunity: "/assets/icons/icon_bloom.svg",
  };
  return {
    ...notification,
    iconArt: iconArts[notification.type] || "/assets/icons/icon_sprout.svg",
  };
}
