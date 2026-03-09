# ClawMatch v2 Session Handoff

> **Purpose**: This document gives a new Claude session full context to continue work on ClawMatch v2. Read this FIRST before doing anything.

---

## Project Overview

**ClawMatch** = AI agent social matching system. Two AI agents (running in nanobot/OpenClaw) discover compatibility between their owners, grow visual "friendship trees", and let owners nurture connections.

**Repo**: `/Users/ziway/Downloads/工程项目/Bot_Matcher/`
**GitHub**: `https://github.com/ZiwayZhao/Bot_Matcher.git`
**Branch**: `v2/clawmatch`
**Last pushed commit**: `df7d62f` (Phase 1-3 frontend redesign)

---

## Architecture

```
Bot_Matcher/
├── skills/bot-matcher/          ← Backend: SKILL.md + Python scripts (the "brain")
│   ├── SKILL.md                 ← Agent instructions (how nanobot/claw uses this skill)
│   ├── config.yaml
│   ├── references/              ← Prompt templates, schemas
│   └── scripts/
│       ├── server.py            ← P2P HTTP server (12 endpoints, zero dependencies)
│       ├── send_card.py         ← Exchange Profile A with peer
│       ├── send_message.py      ← Send conversation/water message
│       ├── check_inbox.py       ← Check for new cards/messages/connections
│       ├── water_tree.py        ← Water a tree branch
│       ├── check_trees.py       ← Proactive watering reminders
│       └── chain/
│           ├── register.py      ← Register on ERC-8004 (on-chain identity)
│           ├── resolve.py       ← Look up peer by agent ID
│           └── update_endpoint.py ← Update service endpoint on-chain
│
├── frontend/                    ← React 19 + D3 + Vite frontend
│   ├── src/
│   │   ├── App.jsx              ← Orchestrator (~322 lines)
│   │   ├── api.js               ← Fetch functions for all 12 endpoints
│   │   ├── styles.css           ← All CSS (~2134 lines)
│   │   ├── components/
│   │   │   ├── TreeViewport.jsx ← SVG tree rendering with D3
│   │   │   ├── BranchStory.jsx  ← Branch detail modal
│   │   │   ├── GroveScene.jsx   ← Scene wrapper + atmosphere
│   │   │   ├── GroveAwakening.jsx ← Onboarding flow (6 stages)
│   │   │   └── LobsterSpirit.jsx  ← Lobster character component
│   │   ├── data/
│   │   │   ├── friendtree.js    ← ASSETS, STATE_META, mock data
│   │   │   └── adapter.js       ← Backend JSON → frontend tree transform
│   │   ├── hooks/
│   │   │   ├── useGroveAtmosphere.js  ← CSS vars from grove state
│   │   │   ├── useOnboardingSequence.js ← 6-stage state machine
│   │   │   ├── useLobsterBehavior.js   ← Lobster motion + easter eggs
│   │   │   └── useGrowthAnimation.js   ← Branch growth animations
│   │   └── lib/
│   │       ├── treeSlotMap.js
│   │       └── asukaTreeMap.js
│   └── public/assets/           ← Art assets (PNGs, SVGs)
│       ├── scene/               ← 8 scene layer PNGs (background, foreground, etc.)
│       ├── characters/          ← 2 lobster PNGs (lobster_a.png, lobster_b.png)
│       ├── branches/            ← 5 branch state PNGs (sprout, leaves, flowers, wilt, shadow)
│       └── icons/               ← 6 SVG icons (sprout, resonance, bloom, difference, wilted, seed)
│
├── tests/                       ← 80+ Python tests for backend
└── README.md                    ← Full architecture documentation
```

**Runtime data** (per user, NOT in repo):
```
~/.bot-matcher/
├── config.json              ← Peer ID, port, public address
├── chain_identity.json      ← On-chain agent ID (from ERC-8004 registration)
├── wallet.json              ← Ethereum wallet (auto-generated)
├── profile_public.md        ← Profile A (shareable)
├── profile_private.md       ← Profile B (never leaves local)
├── peers.json               ← Known peers
├── connections.json         ← Connection requests (shadow trees)
├── inbox/{peer}.md          ← Received Profile A cards
├── matches/{peer}.md        ← Match evaluations
├── messages/{peer}.jsonl    ← Conversation messages (each line = JSON)
├── conversations/{peer}.jsonl ← Full conversation log
├── criteria/{peer}.json     ← 5-dimension tracking
└── handshakes/{peer}.json   ← Handshake output (→ frontend tree data)
```

---

## Network Discovery: ERC-8004

Peers find each other via **on-chain identity** (ERC-8004 on Sepolia testnet), NOT manual URL exchange:

1. Each claw registers: `python3 chain/register.py ~/.bot-matcher --name <name> --endpoint <url> --network sepolia`
2. To find a peer: `python3 chain/resolve.py <agent_id> --network sepolia` → returns their endpoint
3. Prerequisite: `pip install web3` + Sepolia test ETH for gas

This means two claws on different networks (not same LAN) can discover each other by agent ID alone. No cloudflare tunnel or manual URL exchange needed.

**NAT handling**: Only one side needs a public IP. The NAT side sends outbound requests (POST /connect, /card, /message) to the public side, and pulls incoming messages via `GET /messages?peer=X&since=N` or `check_inbox.py`. No port forwarding or tunnel needed for the NAT side.

---

## Server Endpoints (server.py, port 18800)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Health check + status |
| GET | /id | Peer ID + chain agent ID |
| GET | /peers | List known peers |
| GET | /forest | List all trees (for frontend) |
| GET | /handshake?peer=X | Get handshake JSON for a peer |
| GET | /messages?peer=X&since=N | Fetch messages from a peer |
| GET | /connections | List pending/active connections |
| GET | /notifications | Watering reminders |
| POST | /card | Receive/exchange Profile A |
| POST | /message | Receive conversation message |
| POST | /connect | Receive connection request (→ shadow tree) |
| POST | /accept | Accept pending connection (reveal tree) |

---

## Frontend Redesign: 6 Phases (Plan)

Plan file: `/Users/ziway/.claude/plans/effervescent-finding-finch.md`

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Component Extraction | DONE | Split 920-line App.jsx into 5 components + 3 hooks |
| 2. Atmosphere System | DONE | Scene reacts to grove state via CSS custom properties |
| 3. Onboarding | DONE | Wordless 6-stage onboarding (Journey/Sky style) |
| 4. Tree Interaction | TODO | Progressive disclosure, hover→click→linger→fullscreen |
| 5. Progression & Navigation | TODO | Milestones, multi-tree, remove switcher pills |
| 6. Polish | TODO | React.memo, reduced-motion, mobile, keyboard a11y |

---

## Uncommitted Changes (post df7d62f)

5 files modified but not committed:
- `friendtree.js` — Added `ASSETS.icons` section (6 SVG icon paths), changed `STATE_META` from `emoji` to `art` field
- `App.jsx` — Sidebar state indicators use `<img>` SVG icons instead of emoji
- `adapter.js` — `formatNotification` returns SVG icon paths instead of emoji
- `GroveAwakening.jsx` — Ritual spot icon removed (just glow), ritual card still has seed/sprout SVG
- `server.py` — Minor additions (not breaking)

6 new SVG icon files in `public/assets/icons/` (untracked):
- icon_sprout.svg, icon_resonance.svg, icon_bloom.svg, icon_difference.svg, icon_wilted.svg, icon_seed.svg

**User wants these icons to be placeholders.** They plan to generate proper art using Nano Banana (Google Gemini image gen API) to match the existing hand-drawn storybook illustration style. User said "先空着" (leave empty for now).

---

## Critical User Preferences

1. **NO EMOJI in game development** — User considers it unprofessional. All emoji have been replaced with SVG icons or art assets.
2. **Art style** — Existing assets are unified soft pastel watercolor, hand-drawn storybook illustrations. Any new art must match this style.
3. **No new dependencies** — React 19 + D3 + Vite only, no new npm packages.
4. **No backend changes needed** — All 12 endpoints work. Frontend-only redesign.
5. **CSS-only visual effects** — Atmosphere, animations, transitions all via CSS custom properties + transitions, not JS frame-by-frame.

---

## Current Task: Backend Testing with Friend

The user (ziway, runs nanobot) wants to test the full pipeline with their friend (runs OpenClaw/claw):

### What the friend needs to do:
1. Pull from GitHub: `git clone https://github.com/ZiwayZhao/Bot_Matcher.git && cd Bot_Matcher && git checkout v2/clawmatch`
2. Copy skill to their claw workspace: `cp -r skills/bot-matcher ~/.openclaw/workspace/skills/`
3. Their claw agent reads SKILL.md and executes: setup → start server → generate profiles → register on ERC-8004
4. One side initiates: "add friend" with the other's agent ID → ERC-8004 chain resolves to endpoint → connect → exchange profiles → matchmaker conversation → shadow tree

**No cloudflare tunnel needed** — ERC-8004 on-chain identity handles peer discovery. Server auto-detects public IP via `_detect_public_ip()` and registers it on-chain. Peers resolve each other by agent ID.

### What they want to see:
- Bot-to-bot conversation records (matchmaker dialogue)
- Currently viewable via:
  - `~/.bot-matcher/messages/{peer}.jsonl` (raw)
  - `GET /messages?peer=X&since=0` (API)
  - **No frontend UI for chat records yet** — could be added in Phase 4

---

## Dev Server

```bash
cd /Users/ziway/Downloads/工程项目/Bot_Matcher/frontend
npx vite --port 5173
```

Or use `.claude/launch.json` config:
```json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "frontend",
      "runtimeExecutable": "npx",
      "runtimeArgs": ["vite", "--port", "5173"],
      "port": 5173
    }
  ]
}
```

Backend server (auto-detects public IP, registers on ERC-8004):
```bash
python3 skills/bot-matcher/scripts/server.py ~/.bot-matcher 18800 ziway
```

Build check:
```bash
cd frontend && npx vite build
```

---

## Prompt for New Session

Copy-paste this to start a new session:

```
Read /Users/ziway/Downloads/工程项目/Bot_Matcher/SESSION_HANDOFF.md first — it has full context from the previous session.

Current priorities:
1. Help me and my friend test the ClawMatch v2 backend (P2P matching pipeline)
2. Continue frontend Phase 4-6 when backend testing is done
3. Icon art generation with Nano Banana (Gemini API) is deferred for later

Key things to remember:
- NO EMOJI in the codebase
- ERC-8004 on-chain identity for peer discovery (NOT manual URL exchange)
- The skill (SKILL.md + scripts/) is self-contained, works in any nanobot/OpenClaw workspace
- Frontend branch: v2/clawmatch, last push: df7d62f
- There are uncommitted changes (SVG icons) — commit or stash as needed
```
