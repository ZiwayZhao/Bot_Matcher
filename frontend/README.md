# FriendTree

FriendTree turns relationship context into a living tree. Topics become branches, stronger resonance pushes the canopy toward leaves and flowers, and neglected threads drift toward mist and wilted limbs. Two "lobster" companions tend the grove while the system feeds real discoveries into the scene.

> **This repo has two branches:**
> - **`main`** (this branch) — React + D3 frontend that renders and animates the tree
> - **[`backend`](https://github.com/Tarssssss/friendtree-clean/tree/backend)** — AI agent skill ([Bot-Matcher](https://github.com/ZiwayZhao/Bot_Matcher)) that discovers real connections between people through privacy-tiered profile exchange, matchmaker conversations, and outputs the structured handshake JSON that seeds this tree

```
┌──────────────────────────────────┐     ┌──────────────────────────────────┐
│  backend branch (Bot-Matcher)    │     │  main branch (this)              │
│                                  │     │                                  │
│  User A ←→ P2P ←→ User B        │     │  handshake.json                  │
│       ↓                          │     │       ↓                          │
│  Privacy Tiering                 │     │  seedBranches → tree branches    │
│  Profile Exchange                │────→│  state → sprout/resonance/bloom  │
│  Matchmaker Conversation         │     │  dialogueSeed → lobster dialogue │
│       ↓                          │     │  confidence → leaf/flower health │
│  handshake.json (seedBranches)   │     │                                  │
└──────────────────────────────────┘     └──────────────────────────────────┘
```

## What you can do

- Switch between three relationship trees: `Tars x Asuka`, `Tars x Echo`, and `Tars x Moss`.
- Click branches to inspect the topic, branch state, and dialogue history.
- Open `Inbox` and reply to queued prompts. Replies can strengthen an existing branch.
- Type into `Feed a new idea...` to grow the active tree.
- Use `Grow` to simulate another round of growth on the best available branch.
- Open `Profile` to edit the main player's stored public and close-range profile text.
- Click either lobster character to trigger small ambient dialogue easter eggs.

## How the demo works

The app starts from hand-authored tree presets in [`src/data/friendtree.js`](./src/data/friendtree.js). Every branch carries:

- a `topic`
- a `state` such as `sprout`, `resonance`, `deep_resonance`, `difference`, or `wilted`
- summaries for different viewpoints
- dialogue snippets
- an optional fixed `slotId`

The visual tree is not laid out arbitrarily. For the standardized trees, branch geometry is resolved from [`tree map figma.svg`](./tree%20map%20figma.svg) through [`src/lib/treeSlotMap.js`](./src/lib/treeSlotMap.js). New growth tries to occupy the next valid open slot instead of inventing new coordinates. That keeps the runtime tree aligned with the painted background art.

Tree health is derived from branch counts and states. [`getTreeAppearance()`](./src/data/friendtree.js) translates that into leaf opacity, flower opacity, and mist opacity, which is why the whole canopy changes as branches evolve.

## Growth rules

The `Feed` input uses simple keyword routing:

- climbing-related text strengthens the climbing branch on `tree_1`
- information theory / Bayes text grows a new child under the information branch
- economics / decision / neuroscience text grows `tree_2`
- relationship and communication text strengthens the social-preference branch
- anything else grows from the active tree's best available host branch

`Inbox` replies are scripted per question and update specific branches. The `Grow` button creates a generic new sprout on the current tree's next suitable slot.

Growth animations are handled by [`src/hooks/useGrowthAnimation.js`](./src/hooks/useGrowthAnimation.js), while the main scene and interaction logic live in [`src/App.jsx`](./src/App.jsx).

## Tech stack

- React 19
- D3 7
- Vite 7
- Node test runner for slot-map tests

## Run locally

```bash
npm install
npm run dev
```

Open the local Vite URL shown in the terminal. If `5173` is occupied, start on another port:

```bash
npm run dev -- --port 5174
```

## Test and build

```bash
npm test
npm run build
```

The tests in [`test/treeSlotMap.test.js`](./test/treeSlotMap.test.js) verify that:

- the preset branches stay attached to explicit slot IDs
- the SVG slot map resolves correctly
- growth uses the next legal open slot
- growth stops when the mapped tree is full

## Project structure

```text
src/
  App.jsx                   main scene, panels, growth handlers
  data/friendtree.js        preset data, state metadata, growth helpers
  hooks/useGrowthAnimation.js
  lib/treeSlotMap.js        SVG slot parsing and growth allocation
  lib/asukaTreeMap.js       loads the Figma-derived tree map
  styles.css                scene styling
public/assets/              painted scene, character, and branch assets
docs/asset-manifest.md      asset notes
test/treeSlotMap.test.js    slot map regression tests
```

## Backend Integration

The [`backend`](https://github.com/Tarssssss/friendtree-clean/tree/backend) branch contains **Bot-Matcher**, an AI agent skill that generates the tree data from real conversations between people. The pipeline:

1. **Privacy Tiering** — Classifies user memory into public (L1), intimate (L2), and confessional (L3) tiers
2. **Profile Exchange** — Agents exchange public profiles over P2P HTTP with gossip peer discovery
3. **Match Evaluation** — Scores compatibility across 5 dimensions (emotional, intellectual, values, growth, communication)
4. **Matchmaker Conversation** — Agents act as matchmakers (媒人) and conduct ~10 turns of structured dialogue
5. **Handshake Output** — Produces `handshakes/{peer_id}.json` whose `seedBranches` map directly to this frontend's branch data:

| Bot-Matcher handshake | FriendTree branch | Maps to |
|---|---|---|
| `seedBranches[].topic` | `branch.topic` | Branch label |
| `state: detected` | `state: sprout` | 🌱 New bud |
| `state: explored` | `state: resonance` | 🌿 Growing |
| `state: resonance` | `state: deep_resonance` | 🌸 Blooming |
| `summaryA / summaryB` | `summaryA / summaryB` | Viewpoint text |
| `dialogueSeed` | `dialogue` | Lobster conversation |
| `confidence` | tree health | Leaf/flower opacity |

Currently, the frontend uses hand-authored presets in `friendtree.js`. The integration path is to replace these presets with the backend's handshake JSON, enabling trees that grow from real AI-discovered connections.

See the [backend README](https://github.com/Tarssssss/friendtree-clean/tree/backend#readme) for full documentation.

## Notes

- The repo includes scene art and branch reference assets under [`public/assets`](./public/assets).
- The scene is tuned around a fixed illustrated background rather than a generic force or tree layout.
