const CHARACTER_ASSET_VERSION = "2026-03-06-2";

export const ASSETS = {
  scene: {
    background: "/assets/scene/scene_entire_background.png",
    foreground: "/assets/scene/scene_front.png",
    moodboard: "/assets/scene/main_theme.png",
    treeBare: "/assets/scene/tree_no_leaves.png",
    treeLeaves: "/assets/scene/tree_full_leaves.png",
    treeFlowers: "/assets/scene/tree_full_flowers.png",
    treeFlowersCutout: "/assets/scene/tree_full_flowers_cutout.png",
    treeRoot: "/assets/scene/tree_root.png",
  },
  characters: {
    lobsterA: `/assets/characters/lobster_a_new.png?v=${CHARACTER_ASSET_VERSION}`,
    lobsterB: `/assets/characters/lobster_b_new.png?v=${CHARACTER_ASSET_VERSION}`,
  },
  branches: {
    sprout: "/assets/branches/branch_sprout.png",
    resonance: "/assets/branches/branch_grow.png",
    deep_resonance: "/assets/branches/branch_bloom.png",
    difference: "/assets/branches/branch_flower.png",
    wilted: "/assets/branches/branch_wilt.png",
  },
  icons: {
    sprout: "/assets/icons/icon_sprout.svg",
    resonance: "/assets/icons/icon_resonance.svg",
    deep_resonance: "/assets/icons/icon_bloom.svg",
    difference: "/assets/icons/icon_difference.svg",
    wilted: "/assets/icons/icon_wilted.svg",
    seed: "/assets/icons/icon_seed.svg",
  },
};

export const USERS = {
  user_a: {
    id: "user_a",
    name: "Tars",
    lobster: "Ember",
    emoji: "🦞",
    role: "Caretaker",
    t1: "LBS MiM student with an economics background. Interested in AI systems and platform strategy. Enjoys outdoor sports, climbing, and information theory. Based in London.",
    t2: "Prefers one-on-one conversations. Hopes to meet someone who would climb together and cares a lot about how two people communicate.",
    preferences: {
      likes: "Likes people who are warm, cheerful, and think for themselves.",
      dislikes: "Dislikes people who are overly competitive and obsessed with winning.",
    },
  },
  user_b: {
    id: "user_b",
    name: "Asuka",
    lobster: "Claw",
    emoji: "🦀",
    role: "Co-gardener",
    t1: "Digital artist and interaction designer. Researches urban memory and spatial data visualization. Loves philosophy and frontier technology.",
    t2: "One of her dating criteria is hoping the other person climbs too. Her public image and private life feel strikingly different.",
  },
  user_c: {
    id: "user_c",
    name: "Echo",
    lobster: "Shell",
    emoji: "🐚",
    role: "Interdisciplinary peer",
    t1: "UCL graduate student in cognitive neuroscience. Interested in decision science and behavioral economics. Based in London.",
    t2: "Currently going through a stretch of academic anxiety and looking for an interdisciplinary companion who really gets it.",
  },
  user_d: {
    id: "user_d",
    name: "Moss",
    lobster: "Bubble",
    emoji: "🫧",
    role: "Friend drifting away",
    t1: "Freelance translator living in London. Loves classical music and travel in Southeast Asia, and reads a lot of popular science.",
    t2: "Thinking about changing careers. Curious about AI but has not really entered the field yet.",
  },
};

export const STATE_META = {
  sprout: {
    label: "Sprout",
    tagLabel: "Sprout",
    art: ASSETS.icons.sprout,
    color: "#9dc770",
    accent: "#e9f4ca",
    description: "A new direction has just appeared and is waiting for the next reply.",
  },
  resonance: {
    label: "Resonance",
    tagLabel: "Resonance",
    art: ASSETS.icons.resonance,
    color: "#77ae79",
    accent: "#dcf0dc",
    description: "Both sides have left real energy here.",
  },
  deep_resonance: {
    label: "Bud",
    tagLabel: "Bud",
    art: ASSETS.icons.deep_resonance,
    color: "#d8ae76",
    accent: "#fbefd8",
    description: "This branch is close to blooming. It is one of the warmest places in the tree.",
  },
  difference: {
    label: "Difference",
    tagLabel: "Diverge",
    art: ASSETS.icons.difference,
    color: "#92b0c2",
    accent: "#e5f1f8",
    description: "It has not dried out. It just leaned toward a different path of understanding.",
  },
  wilted: {
    label: "Wilted",
    tagLabel: "Wilted",
    art: ASSETS.icons.wilted,
    color: "#b9a89d",
    accent: "#efe6df",
    description: "This branch has not been cared for lately.",
  },
};

export const TREE_GUIDES = {
  tree_1: {
    root: { x: 686, y: 654 },
    nodes: {
      b1: {
        x: 446,
        y: 548,
        c1x: 646,
        c1y: 612,
        c2x: 520,
        c2y: 598,
        labelDx: -86,
        labelDy: -84,
      },
      b4: {
        x: 420,
        y: 382,
        c1x: 446,
        c1y: 504,
        c2x: 426,
        c2y: 434,
        labelDx: -64,
        labelDy: -82,
      },
      b6: {
        x: 390,
        y: 246,
        c1x: 412,
        c1y: 338,
        c2x: 398,
        c2y: 284,
        labelDx: -54,
        labelDy: -80,
      },
      b2: {
        x: 604,
        y: 534,
        c1x: 676,
        c1y: 606,
        c2x: 628,
        c2y: 586,
        labelDx: -72,
        labelDy: -84,
      },
      b7: {
        x: 642,
        y: 356,
        c1x: 622,
        c1y: 470,
        c2x: 646,
        c2y: 414,
        labelDx: -88,
        labelDy: -82,
      },
      b3: {
        x: 864,
        y: 548,
        c1x: 688,
        c1y: 612,
        c2x: 804,
        c2y: 594,
        labelDx: -86,
        labelDy: -84,
      },
      b8: {
        x: 926,
        y: 392,
        c1x: 884,
        c1y: 506,
        c2x: 926,
        c2y: 444,
        labelDx: -66,
        labelDy: -80,
      },
      b5: {
        x: 1088,
        y: 620,
        c1x: 698,
        c1y: 620,
        c2x: 1000,
        c2y: 638,
        labelDx: -84,
        labelDy: -84,
      },
    },
    childSlots: {
      root: [
        { x: 446, y: 548, c1x: 616, c1y: 754, c2x: 500, c2y: 600 },
        { x: 604, y: 534, c1x: 652, c1y: 730, c2x: 618, c2y: 600 },
        { x: 864, y: 548, c1x: 758, c1y: 762, c2x: 826, c2y: 616 },
        { x: 1088, y: 620, c1x: 968, c1y: 704, c2x: 1040, c2y: 660 },
      ],
      b1: [
        { x: 332, y: 608, c1x: 404, c1y: 562, c2x: 360, c2y: 594 },
        { x: 420, y: 382, c1x: 446, c1y: 504, c2x: 426, c2y: 434 },
        { x: 324, y: 708, c1x: 402, c1y: 624, c2x: 352, c2y: 678 },
        { x: 244, y: 790, c1x: 322, c1y: 742, c2x: 274, c2y: 776 },
      ],
      b4: [
        { x: 390, y: 246, c1x: 412, c1y: 338, c2x: 398, c2y: 284 },
        { x: 468, y: 304, c1x: 434, c1y: 360, c2x: 456, c2y: 324 },
        { x: 356, y: 314, c1x: 404, c1y: 344, c2x: 370, c2y: 320 },
      ],
      b6: [
        { x: 470, y: 190, c1x: 404, c1y: 236, c2x: 446, c2y: 210 },
        { x: 520, y: 134, c1x: 444, c1y: 214, c2x: 498, c2y: 170 },
      ],
      b2: [
        { x: 532, y: 436, c1x: 586, c1y: 500, c2x: 548, c2y: 452 },
        { x: 642, y: 356, c1x: 622, c1y: 470, c2x: 646, c2y: 414 },
        { x: 712, y: 286, c1x: 648, c1y: 354, c2x: 692, c2y: 320 },
      ],
      b7: [
        { x: 562, y: 280, c1x: 614, c1y: 330, c2x: 580, c2y: 294 },
        { x: 742, y: 250, c1x: 654, c1y: 316, c2x: 714, c2y: 274 },
        { x: 786, y: 172, c1x: 730, c1y: 246, c2x: 774, c2y: 198 },
      ],
      b3: [
        { x: 924, y: 392, c1x: 882, c1y: 506, c2x: 924, c2y: 444 },
        { x: 1008, y: 300, c1x: 946, c1y: 366, c2x: 992, c2y: 326 },
        { x: 1112, y: 350, c1x: 1004, c1y: 306, c2x: 1072, c2y: 332 },
      ],
      b8: [
        { x: 1066, y: 366, c1x: 958, c1y: 398, c2x: 1032, c2y: 364 },
        { x: 1140, y: 322, c1x: 1024, c1y: 334, c2x: 1106, c2y: 316 },
        { x: 1220, y: 282, c1x: 1100, c1y: 308, c2x: 1188, c2y: 274 },
        { x: 1280, y: 236, c1x: 1168, c1y: 266, c2x: 1252, c2y: 244 },
      ],
      b5: [
        { x: 1182, y: 690, c1x: 1104, c1y: 642, c2x: 1150, c2y: 678 },
        { x: 1266, y: 622, c1x: 1142, c1y: 620, c2x: 1232, c2y: 618 },
        { x: 1170, y: 754, c1x: 1106, c1y: 682, c2x: 1150, c2y: 730 },
      ],
    },
  },
};

export const TREE_SKELETONS = {
  tree_1: {
    size: { width: 2816, height: 1536 },
    root: [1412, 1292],
    slots: {
      "root->b1": {
        points: [
          [1412, 1292],
          [1388, 1270],
          [1344, 1240],
          [1286, 1206],
          [1216, 1172],
          [1146, 1146],
          [1080, 1130],
          [1026, 1122],
        ],
      },
      "b1->b4": {
        points: [
          [1026, 1122],
          [990, 1078],
          [958, 1032],
          [926, 990],
          [896, 958],
          [864, 938],
        ],
      },
      "b4->b6": {
        points: [
          [864, 938],
          [850, 884],
          [832, 838],
          [804, 804],
          [774, 784],
          [740, 776],
        ],
      },
      "root->b2": {
        points: [
          [1412, 1292],
          [1410, 1252],
          [1408, 1206],
          [1402, 1156],
          [1390, 1104],
          [1374, 1064],
          [1348, 1046],
          [1294, 1040],
        ],
      },
      "b2->b7": {
        points: [
          [1294, 1040],
          [1290, 970],
          [1294, 904],
          [1308, 830],
          [1328, 746],
          [1352, 650],
        ],
      },
      "root->b3": {
        points: [
          [1412, 1292],
          [1450, 1260],
          [1504, 1222],
          [1566, 1178],
          [1632, 1134],
          [1696, 1088],
          [1738, 1056],
          [1758, 1048],
        ],
      },
      "b3->b8": {
        points: [
          [1758, 1048],
          [1796, 994],
          [1832, 940],
          [1868, 878],
          [1910, 808],
        ],
      },
      "root->b5": {
        points: [
          [1412, 1292],
          [1498, 1288],
          [1610, 1286],
          [1740, 1284],
          [1888, 1280],
          [2052, 1276],
          [2218, 1270],
          [2364, 1264],
        ],
      },
    },
    childSlots: {
      b1: [
        {
          points: [
            [1026, 1122],
            [924, 1082],
            [818, 1086],
            [706, 1116],
          ],
        },
        {
          points: [
            [1026, 1122],
            [964, 1198],
            [904, 1256],
            [846, 1296],
          ],
        },
        {
          points: [
            [1026, 1122],
            [928, 1168],
            [812, 1222],
            [686, 1250],
          ],
        },
      ],
      b4: [
        {
          points: [
            [864, 938],
            [790, 886],
            [722, 848],
            [644, 836],
          ],
        },
        {
          points: [
            [864, 938],
            [852, 842],
            [862, 732],
            [904, 632],
          ],
        },
      ],
      b6: [
        {
          points: [
            [740, 776],
            [658, 736],
            [572, 706],
            [474, 694],
          ],
        },
        {
          points: [
            [740, 776],
            [684, 690],
            [632, 596],
            [594, 500],
          ],
        },
      ],
      b2: [
        {
          points: [
            [1294, 1040],
            [1222, 958],
            [1136, 902],
            [1036, 880],
          ],
        },
      ],
      b7: [
        {
          points: [
            [1352, 650],
            [1278, 574],
            [1188, 510],
            [1086, 466],
          ],
        },
        {
          points: [
            [1352, 650],
            [1414, 566],
            [1490, 480],
            [1584, 404],
          ],
        },
      ],
      b3: [
        {
          points: [
            [1758, 1048],
            [1866, 1012],
            [1988, 998],
            [2126, 994],
          ],
        },
        {
          points: [
            [1758, 1048],
            [1836, 1106],
            [1942, 1162],
            [2076, 1208],
          ],
        },
      ],
      b8: [
        {
          points: [
            [1910, 808],
            [2028, 770],
            [2160, 728],
            [2296, 668],
          ],
        },
        {
          points: [
            [1910, 808],
            [2034, 826],
            [2164, 854],
            [2284, 900],
          ],
        },
      ],
      b5: [
        {
          points: [
            [2364, 1264],
            [2458, 1262],
            [2556, 1260],
            [2658, 1258],
          ],
        },
      ],
    },
  },
};

export const TREE_LABEL_LAYOUTS = {
  tree_1: {
    b1: { dx: -228, dy: -94 },
    b4: { dx: -212, dy: -88 },
    b6: { dx: -176, dy: -84 },
    b2: { dx: -186, dy: -94 },
    b7: { dx: -192, dy: -86 },
    b3: { dx: -186, dy: -94 },
    b8: { dx: -150, dy: -86 },
    b5: { dx: -170, dy: -90 },
  },
};

function branch({
  id,
  slotId,
  topic,
  state,
  summaryA,
  summaryB,
  dialogue,
  children = [],
}) {
  return {
    id,
    slotId,
    topic,
    state,
    summaryA,
    summaryB,
    dialogue,
    children,
  };
}

const TREE_PRESETS = {
  tree_1: {
    id: "tree_1",
    label: "Tars × Asuka",
    subtitle: "The main tree they are caring for together",
    partnerId: "user_b",
    sceneStatus: "This tree already has clear layers. The higher branches are getting closer to blooming.",
    root: {
      id: "root",
      topic: "FriendTree",
      isRoot: true,
      children: [
        branch({
          id: "b1",
          slotId: "1",
          topic: "Frontier Tech",
          state: "resonance",
          summaryA: "You found a stable resonance at the intersection of technology and creation.",
          summaryB: "The two claws always circle back to this branch when they talk about systems, expression, and tech.",
          dialogue: [
            { speaker: "Ember", text: "My human is especially obsessed with AI agent design." },
            { speaker: "Claw", text: "My human is an artist, but she goes deep into computation and data visualization too." },
          ],
          children: [
            branch({
              id: "b4",
              slotId: "1-1",
              topic: "Information Theory",
              state: "sprout",
              summaryA: "The claws found a theoretical direction worth digging into.",
              summaryB: "It feels like a thin branch reaching upward, waiting for the next serious reply.",
              dialogue: [
                { speaker: "Ember", text: "My human has always been interested in Shannon entropy and Bayesian updates." },
              ],
              children: [
                branch({
                  id: "b6",
                  slotId: "1-1-1",
                  topic: "Bayesian",
                  state: "sprout",
                  summaryA: "If you keep feeding this direction, it will grow into a higher layer.",
                  summaryB: "This is already a probe above a second-level topic.",
                  dialogue: [
                    { speaker: "Claw", text: "Maybe we should keep asking along the line of updating and judgment." },
                  ],
                }),
              ],
            }),
          ],
        }),
        branch({
          id: "b2",
          slotId: "2",
          topic: "Climbing",
          state: "deep_resonance",
          summaryA: "This is one of the most special buds, carrying a private preference and a real spark.",
          summaryB: "Through sports, the claws touched a layer that feels more private and more real.",
          dialogue: [
            { speaker: "Ember", text: "My human climbs sometimes, but he does not usually bring it up first." },
            { speaker: "Claw", text: "One of my human's dating criteria is hoping the other person climbs too." },
            { speaker: "Ember", text: "He used to go to Yosemite often when he was studying in the US." },
            { speaker: "Claw", text: "She is definitely going to remember that detail." },
          ],
          children: [
            branch({
              id: "b7",
              slotId: "2-1",
              topic: "Yosemite",
              state: "deep_resonance",
              summaryA: "This high branch is close to blooming. The jump came from a vivid personal memory.",
              summaryB: "Once the conversation lands on a real place and real experience, the tree grows unusually fast.",
              dialogue: [
                { speaker: "Ember", text: "What happened in Yosemite means much more than a casual hobby to him." },
                { speaker: "Claw", text: "This is no longer generic small talk. It is the kind of experience that makes someone listen carefully." },
              ],
            }),
          ],
        }),
        branch({
          id: "b3",
          slotId: "3",
          topic: "Lifestyle",
          state: "difference",
          summaryA: "Your rhythms are different, but the branch has not lost life because of that difference.",
          summaryB: "The claws know your daily tempos are different, and they are still trying to understand them.",
          dialogue: [
            { speaker: "Ember", text: "My human lives in London, so his pace is steadier." },
            { speaker: "Claw", text: "My human moves between Berlin and Tokyo, so her life changes much more often." },
          ],
          children: [
            branch({
              id: "b8",
              slotId: "3-1",
              topic: "City Rhythm",
              state: "difference",
              summaryA: "This branch leans a little to the side, but it is still alive.",
              summaryB: "Difference is not a bad sign. It just asks for slower understanding.",
              dialogue: [
                { speaker: "Claw", text: "Maybe part of the attraction comes exactly from how different their rhythms are." },
              ],
            }),
          ],
        }),
        branch({
          id: "b5",
          slotId: "4",
          topic: "Social Preferences",
          state: "sprout",
          summaryA: "The first tentative conversation about relationship rhythm has just begun.",
          summaryB: "The other claw has already brought in a more private kind of social information.",
          dialogue: [
            { speaker: "Ember", text: "My human prefers one-on-one, deeper conversation." },
          ],
        }),
      ],
    },
  },
  tree_2: {
    id: "tree_2",
    label: "Tars × Echo",
    subtitle: "A tree that has only just begun to sprout",
    partnerId: "user_c",
    sceneStatus: "This tree is still early, but the layered structure has already begun to form.",
    root: {
      id: "root",
      topic: "FriendTree",
      isRoot: true,
      children: [
        branch({
          id: "c1",
          slotId: "1",
          topic: "Academia",
          state: "resonance",
          summaryA: "In academic life, the two of you already share a stable language.",
          summaryB: "This branch grew out of taking the world seriously and thinking about it carefully.",
          dialogue: [
            { speaker: "Ember", text: "My human studies MiM at LBS and comes from economics." },
            { speaker: "Shell", text: "My human studies cognitive neuroscience at UCL." },
          ],
          children: [
            branch({
              id: "c2",
              slotId: "1-1",
              topic: "Interdisciplinary",
              state: "sprout",
              summaryA: "If the conversation keeps going, this could become a very beautiful branch.",
              summaryB: "This is exactly the kind of slim sprout that deserves another question.",
              dialogue: [
                { speaker: "Shell", text: "My human works on decision neuroscience, so it overlaps with economics." },
              ],
              children: [
                branch({
                  id: "c4",
                  slotId: "1-1-1",
                  topic: "Decision-Making",
                  state: "sprout",
                  summaryA: "This branch is already starting to stretch into a third layer.",
                  summaryB: "If it keeps getting fed, it will pull the whole tree upward by a lot.",
                  dialogue: [
                    { speaker: "Ember", text: "Maybe the best way in is through the most concrete questions in behavioral economics." },
                  ],
                }),
              ],
            }),
          ],
        }),
        branch({
          id: "c3",
          slotId: "2",
          topic: "London",
          state: "sprout",
          summaryA: "Living in the same city adds a light but real layer of possibility to this tree.",
          summaryB: "The city itself gives the two of you a shared backdrop to unfold slowly.",
          dialogue: [{ speaker: "Ember", text: "My human lives in London." }],
        }),
      ],
    },
  },
  tree_3: {
    id: "tree_3",
    label: "Tars × Moss",
    subtitle: "A tree someone is still trying to hold on to",
    partnerId: "user_d",
    sceneStatus: "Some old branches have loosened, but the roots have not completely run out of patience.",
    root: {
      id: "root",
      topic: "FriendTree",
      isRoot: true,
      children: [
        branch({
          id: "d1",
          slotId: "1",
          topic: "Reading",
          state: "resonance",
          summaryA: "Reading is still holding this tree up. It is the most stable of the old branches.",
          summaryB: "This connection has not fully stopped; shared reading is still supporting it.",
          dialogue: [
            { speaker: "Ember", text: "My human likes nonfiction." },
            { speaker: "Bubble", text: "Mine too, especially popular science." },
          ],
          children: [
            branch({
              id: "d4",
              slotId: "1-1",
              topic: "AI Tools",
              state: "sprout",
              summaryA: "Ember is trying to rebuild the connection from a different angle.",
              summaryB: "This sprout is one of the last few attempts to grow something new on top of an old relationship.",
              dialogue: [
                { speaker: "Ember", text: "My human has been using AI to build a learning system lately." },
              ],
            }),
          ],
        }),
        branch({
          id: "d2",
          slotId: "2",
          topic: "Music",
          state: "wilted",
          summaryA: "It has not died. It just has not been watered in a while.",
          summaryB: "The topic of music has not been picked up again for a long time.",
          dialogue: [{ speaker: "Bubble", text: "My human likes classical music." }],
        }),
        branch({
          id: "d3",
          slotId: "3",
          topic: "Travel",
          state: "wilted",
          summaryA: "This branch feels quiet, like it has been left behind.",
          summaryB: "Travel came up once, but it never really extended further.",
          dialogue: [{ speaker: "Bubble", text: "My human loves traveling in Southeast Asia." }],
        }),
      ],
    },
  },
};

export const INITIAL_QUESTIONS = [
  {
    id: "q1",
    text: "Do you prefer indoor climbing or outdoor routes? Have you been climbing recently?",
    treeId: "tree_1",
    branchId: "b2",
    answered: false,
  },
  {
    id: "q2",
    text: "How familiar are you with cognitive neuroscience? Which direction in economics would you most want to keep exploring?",
    treeId: "tree_2",
    branchId: "c2",
    answered: false,
  },
  {
    id: "q3",
    text: "What kind of person would you actually want to spend time with offline?",
    treeId: "tree_3",
    branchId: "d4",
    answered: false,
  },
];

function clone(value) {
  return structuredClone(value);
}

function traverse(node, visitor) {
  if (!node) return;
  visitor(node);
  (node.children || []).forEach((child) => traverse(child, visitor));
}

export function createInitialTrees() {
  const trees = clone(TREE_PRESETS);
  Object.values(trees).forEach((tree) => {
    tree.appearance = getTreeAppearance(tree);
  });
  return trees;
}

export function collectBranches(tree) {
  const branches = [];
  traverse(tree.root, (node) => {
    if (!node.isRoot) branches.push(node);
  });
  return branches;
}

export function findBranch(tree, branchId) {
  let found = null;
  traverse(tree.root, (node) => {
    if (node.id === branchId) found = node;
  });
  return found;
}

export function updateBranch(tree, branchId, updater) {
  const target = findBranch(tree, branchId);
  if (target) updater(target);
  return target;
}

export function addBranch(tree, parentId, newBranch) {
  const parent = parentId ? findBranch(tree, parentId) : tree.root;
  const host = parent || tree.root;
  host.children = host.children || [];
  host.children.push(newBranch);
  return newBranch;
}

export function findBestGrowthParent(tree) {
  let candidate = null;
  traverse(tree.root, (node) => {
    if (node.isRoot) return;
    if (candidate) return;
    if (node.state === "sprout" || node.state === "resonance") {
      candidate = node;
    }
  });
  return candidate || tree.root.children[0] || tree.root;
}

export function getTreeStats(tree) {
  const stats = {
    total: 0,
    sprout: 0,
    resonance: 0,
    deep_resonance: 0,
    difference: 0,
    wilted: 0,
  };

  traverse(tree.root, (node) => {
    if (node.isRoot) return;
    stats.total += 1;
    stats[node.state] += 1;
  });

  const health = Math.max(
    10,
    Math.min(
      98,
      Math.round(
        (stats.resonance * 22 +
          stats.deep_resonance * 34 +
          stats.sprout * 14 +
          stats.difference * 10 +
          stats.wilted * 5) / Math.max(stats.total, 1),
      ),
    ),
  );

  return { ...stats, health };
}

export function getTreeAppearance(tree) {
  const stats = getTreeStats(tree);
  const leafOpacity = Math.min(
    1,
    0.3 + stats.resonance * 0.09 + stats.deep_resonance * 0.16 + stats.sprout * 0.06,
  );
  const flowerOpacity = Math.min(0.95, 0.05 + stats.deep_resonance * 0.22 + stats.difference * 0.05);
  const mistOpacity = Math.max(
    0.01,
    0.08 -
      stats.resonance * 0.008 -
      stats.deep_resonance * 0.014 -
      stats.sprout * 0.006 +
      stats.wilted * 0.012,
  );

  return {
    leafOpacity,
    flowerOpacity,
    mistOpacity,
  };
}

export function getTreeDepth(tree) {
  let maxDepth = 0;

  function walk(node, depth) {
    if (!node) return;
    if (!node.isRoot) maxDepth = Math.max(maxDepth, depth);
    (node.children || []).forEach((child) => walk(child, depth + 1));
  }

  walk(tree.root, 1);
  return maxDepth;
}

export function nextBranchTopic(text) {
  const trimmed = text.trim();
  if (!trimmed) return "New";
  if (trimmed.length <= 4) return trimmed;
  return trimmed.slice(0, 4);
}

export function cloneTrees(trees) {
  return clone(trees);
}
