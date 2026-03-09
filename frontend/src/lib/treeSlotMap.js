function parseAttributes(rawAttributes) {
  const attributes = {};
  const attributePattern = /([:@A-Za-z_][\w:.-]*)\s*=\s*"([^"]*)"/g;
  let match = attributePattern.exec(rawAttributes);

  while (match) {
    attributes[match[1]] = match[2];
    match = attributePattern.exec(rawAttributes);
  }

  return attributes;
}

function parseSvgMarkup(svgMarkup) {
  const root = { tag: "root", attributes: {}, children: [] };
  const stack = [root];
  const tagPattern = /<\s*(\/?)\s*([A-Za-z][\w:-]*)\s*([^>]*?)(\/?)\s*>/g;
  let match = tagPattern.exec(svgMarkup);

  while (match) {
    const [, isClosing, tag, rawAttributes, isSelfClosing] = match;

    if (isClosing) {
      if (stack.length > 1) stack.pop();
      match = tagPattern.exec(svgMarkup);
      continue;
    }

    const node = {
      tag,
      attributes: parseAttributes(rawAttributes),
      children: [],
    };

    stack[stack.length - 1].children.push(node);

    if (!isSelfClosing) {
      stack.push(node);
    }

    match = tagPattern.exec(svgMarkup);
  }

  return root;
}

function walkSvg(node, visitor) {
  if (!node) return;
  visitor(node);
  (node.children || []).forEach((child) => walkSvg(child, visitor));
}

function extractNumbers(value) {
  return (value.match(/-?\d*\.?\d+(?:e[-+]?\d+)?/gi) || []).map(Number);
}

function mergeBoundingBoxes(boxes) {
  const validBoxes = boxes.filter(Boolean);
  if (!validBoxes.length) return null;

  return validBoxes.reduce(
    (merged, box) => ({
      minX: Math.min(merged.minX, box.minX),
      minY: Math.min(merged.minY, box.minY),
      maxX: Math.max(merged.maxX, box.maxX),
      maxY: Math.max(merged.maxY, box.maxY),
    }),
    {
      minX: validBoxes[0].minX,
      minY: validBoxes[0].minY,
      maxX: validBoxes[0].maxX,
      maxY: validBoxes[0].maxY,
    },
  );
}

function getPathBoundingBox(pathData) {
  const numbers = extractNumbers(pathData);
  if (numbers.length < 2) return null;

  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;

  for (let index = 0; index < numbers.length - 1; index += 2) {
    const x = numbers[index];
    const y = numbers[index + 1];

    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  }

  if (!Number.isFinite(minX) || !Number.isFinite(minY)) return null;

  return { minX, minY, maxX, maxY };
}

function getRectBoundingBox(attributes) {
  const x = Number(attributes.x || 0);
  const y = Number(attributes.y || 0);
  const width = Number(attributes.width || 0);
  const height = Number(attributes.height || 0);

  if (!Number.isFinite(width) || !Number.isFinite(height)) return null;

  return {
    minX: x,
    minY: y,
    maxX: x + width,
    maxY: y + height,
  };
}

function getElementBoundingBox(node) {
  if (!node) return null;

  if (node.tag === "path") {
    return node.attributes.d ? getPathBoundingBox(node.attributes.d) : null;
  }

  if (node.tag === "rect") {
    return getRectBoundingBox(node.attributes);
  }

  return mergeBoundingBoxes((node.children || []).map((child) => getElementBoundingBox(child)));
}

function getBoundingBoxCenter(box) {
  if (!box) return null;
  return {
    x: (box.minX + box.maxX) / 2,
    y: (box.minY + box.maxY) / 2,
  };
}

function getParentSlotId(slotId) {
  if (!slotId.includes("-")) return null;
  return slotId.split("-").slice(0, -1).join("-");
}

function getPointDistance(left, right) {
  if (!left || !right) return Number.POSITIVE_INFINITY;
  return Math.hypot(left.x - right.x, left.y - right.y);
}

function getSimpleCubicPathPoints(pathData) {
  const numbers = extractNumbers(pathData);
  if (numbers.length !== 8) return null;

  return {
    start: { x: numbers[0], y: numbers[1] },
    c1: { x: numbers[2], y: numbers[3] },
    c2: { x: numbers[4], y: numbers[5] },
    end: { x: numbers[6], y: numbers[7] },
  };
}

function buildSimpleCubicPathData({ start, c1, c2, end }) {
  return `M ${start.x} ${start.y} C ${c1.x} ${c1.y} ${c2.x} ${c2.y} ${end.x} ${end.y}`;
}

function normalizePathDirection(pathData, parentCenter) {
  const cubic = getSimpleCubicPathPoints(pathData);
  if (!cubic || !parentCenter) return pathData;

  const startDistance = getPointDistance(cubic.start, parentCenter);
  const endDistance = getPointDistance(cubic.end, parentCenter);

  if (startDistance <= endDistance) return pathData;

  return buildSimpleCubicPathData({
    start: cubic.end,
    c1: cubic.c2,
    c2: cubic.c1,
    end: cubic.start,
  });
}

function getSlotSegments(slotId) {
  return slotId.split("-").map((value) => Number(value));
}

export function compareSlotIds(left, right) {
  const leftSegments = getSlotSegments(left);
  const rightSegments = getSlotSegments(right);
  const maxLength = Math.max(leftSegments.length, rightSegments.length);

  for (let index = 0; index < maxLength; index += 1) {
    const leftValue = leftSegments[index];
    const rightValue = rightSegments[index];

    if (leftValue === undefined) return -1;
    if (rightValue === undefined) return 1;
    if (leftValue !== rightValue) return leftValue - rightValue;
  }

  return 0;
}

function isDirectChildSlot(parentSlotId, childSlotId) {
  if (!parentSlotId) {
    return childSlotId.split("-").length === 1;
  }

  const parentSegments = parentSlotId.split("-");
  const childSegments = childSlotId.split("-");

  if (childSegments.length !== parentSegments.length + 1) return false;

  return parentSegments.every((segment, index) => segment === childSegments[index]);
}

function traverseTree(node, visitor) {
  if (!node) return;
  visitor(node);
  (node.children || []).forEach((child) => traverseTree(child, visitor));
}

export function collectOccupiedSlotIds(tree) {
  const occupiedSlotIds = new Set();

  traverseTree(tree.root, (node) => {
    if (node.isRoot || !node.slotId) return;
    occupiedSlotIds.add(node.slotId);
  });

  return occupiedSlotIds;
}

export function findBranchById(tree, branchId) {
  let found = null;

  traverseTree(tree.root, (node) => {
    if (node.isRoot || found) return;
    if (node.id === branchId) found = node;
  });

  return found;
}

export function findBranchBySlotId(tree, slotId) {
  let found = null;

  traverseTree(tree.root, (node) => {
    if (node.isRoot || found) return;
    if (node.slotId === slotId) found = node;
  });

  return found;
}

export function getPreorderBranches(tree) {
  const branches = [];

  traverseTree(tree.root, (node) => {
    if (!node.isRoot) branches.push(node);
  });

  return branches;
}

export function resolveTreeSlotMap(svgMarkup) {
  const svgTree = parseSvgMarkup(svgMarkup);
  const slotPaths = new Map();
  const slotDots = new Map();
  let rootDot = null;

  walkSvg(svgTree, (node) => {
    const id = node.attributes.id;
    if (!id) return;

    if (id === "dot-root") {
      rootDot = node;
      return;
    }

    const pathMatch = id.match(/^path-(\d+(?:-\d+)*)$/);
    if (pathMatch && node.tag === "path" && node.attributes.d) {
      slotPaths.set(pathMatch[1], {
        pathId: id,
        pathD: node.attributes.d,
      });
      return;
    }

    const dotMatch = id.match(/^dot-(\d+(?:-\d+)*)$/);
    if (!dotMatch) return;

    const box = getElementBoundingBox(node);
    if (!box) return;

    slotDots.set(dotMatch[1], {
      dotId: id,
      box,
    });
  });

  const slotIds = [...slotPaths.keys()]
    .filter((slotId) => slotDots.has(slotId))
    .sort(compareSlotIds);

  const slots = Object.fromEntries(
    slotIds.map((slotId) => {
      const path = slotPaths.get(slotId);
      const dot = slotDots.get(slotId);

      return [
        slotId,
        {
          slotId,
          pathId: path.pathId,
          dotId: dot.dotId,
          pathD: path.pathD,
          dotCenter: getBoundingBoxCenter(dot.box),
          childSlotIds: [],
        },
      ];
    }),
  );

  slotIds.forEach((slotId) => {
    slots[slotId].childSlotIds = slotIds.filter((candidate) =>
      isDirectChildSlot(slotId, candidate),
    );
  });

  slotIds.forEach((slotId) => {
    const parentSlotId = getParentSlotId(slotId);
    const parentCenter = parentSlotId
      ? slots[parentSlotId]?.dotCenter
      : getBoundingBoxCenter(getElementBoundingBox(rootDot));

    slots[slotId].pathD = normalizePathDirection(slots[slotId].pathD, parentCenter);
  });

  return {
    rootDotId: "dot-root",
    rootCenter: getBoundingBoxCenter(getElementBoundingBox(rootDot)),
    rootChildSlotIds: slotIds.filter((slotId) => isDirectChildSlot(null, slotId)),
    slotIds,
    slots,
  };
}

function getNextAvailableChildSlotId(occupiedSlotIds, treeMap, parentSlotId) {
  const childSlotIds = parentSlotId
    ? treeMap.slots[parentSlotId]?.childSlotIds || []
    : treeMap.rootChildSlotIds || [];

  return childSlotIds.find((slotId) => !occupiedSlotIds.has(slotId)) || null;
}

export function findNextTreeGrowthSlot(tree, treeMap, preferredParentId = null) {
  const occupiedSlotIds = collectOccupiedSlotIds(tree);
  const preorderBranches = getPreorderBranches(tree);
  const branchById = new Map(preorderBranches.map((branch) => [branch.id, branch]));
  const candidateParents = [];
  const seenParentIds = new Set();

  if (preferredParentId) {
    const preferredParent = branchById.get(preferredParentId);
    if (preferredParent) {
      candidateParents.push(preferredParent);
      seenParentIds.add(preferredParent.id);
    }
  }

  const preferredIndex = preferredParentId
    ? preorderBranches.findIndex((branch) => branch.id === preferredParentId)
    : -1;
  const fallbackStartIndex = preferredIndex === -1 ? 0 : preferredIndex + 1;

  preorderBranches.slice(fallbackStartIndex).forEach((branch) => {
    if (seenParentIds.has(branch.id)) return;
    if (branch.state !== "sprout" && branch.state !== "resonance") return;
    candidateParents.push(branch);
    seenParentIds.add(branch.id);
  });

  for (const parent of candidateParents) {
    const slotId = getNextAvailableChildSlotId(occupiedSlotIds, treeMap, parent.slotId);
    if (!slotId) continue;

    return {
      parentId: parent.id,
      slotId,
    };
  }

  if (!preferredParentId) {
    const rootSlotId = getNextAvailableChildSlotId(occupiedSlotIds, treeMap, null);
    if (rootSlotId) {
      return {
        parentId: null,
        slotId: rootSlotId,
      };
    }
  }

  return null;
}
