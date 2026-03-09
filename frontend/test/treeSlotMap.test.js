import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import { createInitialTrees, findBranch } from "../src/data/friendtree.js";
import {
  findBranchBySlotId,
  findNextTreeGrowthSlot,
  resolveTreeSlotMap,
} from "../src/lib/treeSlotMap.js";

const treeMapSvg = fs.readFileSync(
  new URL("../tree map figma.svg", import.meta.url),
  "utf8",
);
const treeMap = resolveTreeSlotMap(treeMapSvg);

function getPathEndpoints(pathData) {
  const values = (pathData.match(/-?\d*\.?\d+(?:e[-+]?\d+)?/gi) || []).map(Number);
  return {
    start: { x: values[0], y: values[1] },
    end: { x: values[values.length - 2], y: values[values.length - 1] },
  };
}

function distance(left, right) {
  return Math.hypot(left.x - right.x, left.y - right.y);
}

function createDummyBranch(slotId) {
  return {
    id: `dummy-${slotId}`,
    slotId,
    topic: `Dummy ${slotId}`,
    state: "sprout",
    summaryA: "",
    summaryB: "",
    dialogue: [],
    children: [],
  };
}

function occupyRemainingSlots(tree) {
  const occupied = new Set();

  function walk(node) {
    if (!node) return;
    if (!node.isRoot && node.slotId) occupied.add(node.slotId);
    (node.children || []).forEach(walk);
  }

  walk(tree.root);

  treeMap.slotIds.forEach((slotId) => {
    if (occupied.has(slotId)) return;

    const parentSlotId = slotId.includes("-")
      ? slotId.split("-").slice(0, -1).join("-")
      : null;
    const host = parentSlotId ? findBranchBySlotId(tree, parentSlotId) : tree.root;
    host.children.push(createDummyBranch(slotId));
    occupied.add(slotId);
  });
}

test("tree_1 bootstrap keeps the explicit branch to slot mapping", () => {
  const tree = createInitialTrees().tree_1;

  assert.equal(findBranch(tree, "b1")?.slotId, "1");
  assert.equal(findBranch(tree, "b2")?.slotId, "2");
  assert.equal(findBranch(tree, "b3")?.slotId, "3");
  assert.equal(findBranch(tree, "b5")?.slotId, "4");
  assert.equal(findBranch(tree, "b4")?.slotId, "1-1");
  assert.equal(findBranch(tree, "b6")?.slotId, "1-1-1");
  assert.equal(findBranch(tree, "b7")?.slotId, "2-1");
  assert.equal(findBranch(tree, "b8")?.slotId, "3-1");
});

test("tree_2 and tree_3 also bootstrap onto explicit fixed slots", () => {
  const trees = createInitialTrees();

  assert.equal(findBranch(trees.tree_2, "c1")?.slotId, "1");
  assert.equal(findBranch(trees.tree_2, "c2")?.slotId, "1-1");
  assert.equal(findBranch(trees.tree_2, "c4")?.slotId, "1-1-1");
  assert.equal(findBranch(trees.tree_2, "c3")?.slotId, "2");

  assert.equal(findBranch(trees.tree_3, "d1")?.slotId, "1");
  assert.equal(findBranch(trees.tree_3, "d4")?.slotId, "1-1");
  assert.equal(findBranch(trees.tree_3, "d2")?.slotId, "2");
  assert.equal(findBranch(trees.tree_3, "d3")?.slotId, "3");
});

test("slot map resolves path/dot pairs and group-based dots", () => {
  assert.deepEqual(treeMap.rootChildSlotIds, ["1", "2", "3", "4"]);
  assert.deepEqual(treeMap.slots["1-1"].childSlotIds, ["1-1-1", "1-1-2"]);
  assert.equal(treeMap.slots["2-1-1"].dotId, "dot-2-1-1");
  assert.deepEqual(treeMap.slots["2-1-1"].dotCenter, { x: 806.379, y: 336.683 });
});

test("slot paths are normalized to grow from parent to child", () => {
  const path = treeMap.slots["4-2"].pathD;
  const { start, end } = getPathEndpoints(path);
  const parentCenter = treeMap.slots["4"].dotCenter;
  const childCenter = treeMap.slots["4-2"].dotCenter;

  assert.ok(distance(start, parentCenter) < distance(end, parentCenter));
  assert.ok(distance(end, childCenter) < distance(start, childCenter));
});

test("growth under b4 takes the next open child slot first", () => {
  const tree = createInitialTrees().tree_1;

  assert.deepEqual(findNextTreeGrowthSlot(tree, treeMap, "b4"), {
    parentId: "b4",
    slotId: "1-1-2",
  });
});

test("when the current parent is full, growth falls forward to the next eligible parent", () => {
  const tree = createInitialTrees().tree_1;
  findBranch(tree, "b4")?.children.push(createDummyBranch("1-1-2"));

  assert.deepEqual(findNextTreeGrowthSlot(tree, treeMap, "b4"), {
    parentId: "b5",
    slotId: "4-1",
  });
});

test("other trees now use the same fixed-slot growth allocator", () => {
  const trees = createInitialTrees();

  assert.deepEqual(findNextTreeGrowthSlot(trees.tree_2, treeMap, "c2"), {
    parentId: "c2",
    slotId: "1-1-2",
  });

  assert.deepEqual(findNextTreeGrowthSlot(trees.tree_3, treeMap, "d1"), {
    parentId: "d1",
    slotId: "1-2",
  });
});

test("when every mapped slot is occupied, growth stops instead of inventing geometry", () => {
  const tree = createInitialTrees().tree_1;
  occupyRemainingSlots(tree);

  assert.equal(findNextTreeGrowthSlot(tree, treeMap, "b1"), null);
  assert.equal(findNextTreeGrowthSlot(tree, treeMap), null);
});
