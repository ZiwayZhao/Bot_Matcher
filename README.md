# Bot-Matcher

**Backend engine for [FriendTree](https://github.com/Tarssssss/friendtree-clean)** — an AI agent skill that discovers meaningful connections between people by exchanging privacy-tiered context profiles, then outputs structured data to grow a visual relationship tree.

Bot-Matcher runs as a skill inside [nanobot](https://github.com/pinkponk/nanobot) or [OpenClaw](https://github.com/nicepkg/openclaw). It handles the full matching pipeline: privacy tiering → profile exchange → match evaluation → matchmaker conversation → **handshake output** that feeds into the FriendTree frontend.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Bot-Matcher Skill (this repo)                                  │
│                                                                 │
│  memory.md → Privacy Tiering → Profile A (public)               │
│                              → Profile B (private, local only)  │
│                                     │                           │
│                              P2P HTTP Exchange                  │
│                                     │                           │
│                              Match Evaluation                   │
│                                     │                           │
│                        Matchmaker Conversation (10 turns)       │
│                                     │                           │
│                              Handshake Output                   │
│                         (handshakes/{peer}.json)                │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  FriendTree Frontend (github.com/Tarssssss/friendtree-clean)    │
│                                                                 │
│  handshake.seedBranches  →  Tree branches (topic nodes)         │
│  state: detected/resonance →  sprout / resonance / deep_resonance│
│  summaryA / summaryB     →  Branch summaries for each side      │
│  dialogueSeed            →  Lobster dialogue snippets            │
│  confidence + depth      →  Branch health → leaves / flowers    │
└─────────────────────────────────────────────────────────────────┘
```

## How It Works

### 1. Privacy Tiering
Every piece of information in the user's memory is classified into:
- **L1 (Public)** — safe to share with any peer
- **L2 (Intimate)** — shared only after trust is established
- **L3 (Confessional)** — never leaves the local agent

### 2. Profile Exchange
Two profiles are generated:
- **Profile A** (L1 data) — exchanged with other agents via P2P HTTP
- **Profile B** (L1+L2 data) — stays local, used for deep compatibility scoring

### 3. Match Evaluation
When agents exchange Profile A's, each evaluates compatibility using their own Profile B across 5 dimensions:

| Dimension | What it measures |
|-----------|-----------------|
| Emotional Alignment | Stress handling, vulnerability, support style |
| Intellectual Resonance | Curiosity patterns, thinking depth |
| Value Compatibility | Core priorities and trade-offs |
| Growth Potential | Learning direction, future goals |
| Communication Style Fit | Disagreement handling, conversation rhythm |

### 4. Matchmaker Conversation
High-scoring matches (≥6/10) trigger an agent-to-agent conversation. Each agent acts as a **matchmaker (媒人)** investigating compatibility on behalf of their owner through ~10 turns of phase-controlled dialogue:

- **Icebreak** (turns 1-2): Find initial common ground
- **Explore** (turns 3-5): Systematically probe all 5 dimensions
- **Deep Dive** (turns 6-8): Dig into the most promising areas
- **Report** (turns 9-10): Generate findings for the human owner

### 5. Handshake Output → FriendTree

The final output is a structured JSON at `~/.bot-matcher/handshakes/{peer_id}.json` that maps directly to FriendTree's branch data:

```json
{
  "handshakeId": "handshake_ziway_agent_dl_1709769900",
  "userAId": "ziway",
  "userBId": "agent_dl",
  "purpose": "friend",
  "stage": "enriched",
  "bootstrap": {
    "mode": "seeded",
    "source": "conversation",
    "seedBranches": [
      {
        "seedId": "seed_1",
        "topic": "Climbing",
        "state": "resonance",
        "summaryA": "Both share a passion for outdoor climbing",
        "summaryB": "Through sports, they touched a layer that feels private and real",
        "matchDimension": "emotional_alignment",
        "dialogueSeed": [
          { "speaker": "claw_a", "text": "My person climbs every weekend at the local gym" },
          { "speaker": "claw_b", "text": "Mine too — they say the wall is where they think most clearly" }
        ],
        "confidence": 0.88
      }
    ]
  }
}
```

**Field mapping to FriendTree:**

| Bot-Matcher (handshake) | FriendTree (branch) | Description |
|------------------------|--------------------|-|
| `seedBranches[].topic` | `branch.topic` | Topic name for the tree node |
| `state: detected` | `state: sprout` | Seen in profiles, not yet discussed |
| `state: explored` | `state: resonance` | Discussed and confirmed |
| `state: resonance` | `state: deep_resonance` | Strong mutual connection |
| `summaryA` / `summaryB` | `summaryA` / `summaryB` | Viewpoint summaries for each side |
| `dialogueSeed` | `dialogue` | Lobster/claw conversation snippets |
| `confidence` (0-1) | tree health | Drives leaf/flower opacity |
| `parentSeedId` | `children` nesting | Sub-topics grow as child branches |

## Two-Stage Generation

The handshake is generated in two stages:

1. **Stage 1 (initial)** — After match evaluation, based on Profile A overlap. Seeds are `detected` with generated dialogue starters.
2. **Stage 2 (enriched)** — After the 10-turn matchmaker conversation. Seeds are upgraded to `explored`/`resonance` with real conversation excerpts as dialogue and depth-based confidence scores.

This means FriendTree can render an initial tree immediately after matching, then animate growth as the conversation progresses.

## Install

Copy the skill directory into your nanobot/OpenClaw workspace:

```bash
cp -r skills/bot-matcher /path/to/your/workspace/skills/
```

Or symlink:
```bash
ln -s /path/to/Bot_Matcher/skills/bot-matcher ~/.nanobot/workspace/skills/bot-matcher
```

## Quick Start

```
You: Set up bot-matcher as alice on port 18800
Bot: [creates config, starts server, generates profiles]

You: Connect to https://peer-xyz.trycloudflare.com
Bot: [sends Profile A, receives peer's, evaluates match → 8/10]
Bot: 🤝 Found a connection! Generating initial handshake...

Bot: [starts matchmaker conversation, 10 turns]
Bot: Conversation complete. Handshake enriched with 5 seed branches.

→ ~/.bot-matcher/handshakes/agent_bob.json  (ready for FriendTree)
```

## Project Structure

```
skills/bot-matcher/
├── SKILL.md                        # Agent instruction set (the "brain")
├── scripts/
│   ├── server.py                   # P2P HTTP server with gossip discovery
│   ├── send_card.py                # Exchange Profile A with a peer
│   ├── send_message.py             # Send conversation message
│   ├── check_inbox.py              # Check for new cards/messages/peers
│   └── match_tiered.py             # Two-tier matching (TF-IDF + LLM)
├── references/
│   ├── prompt1_en.md / prompt1_zh.md   # Privacy Tiering prompts
│   ├── prompt2_en.md / prompt2_zh.md   # Profile Extraction prompts
│   ├── conversation_prompt.md          # Matchmaker persona & strategy
│   └── schemas.md                      # All data schemas (incl. handshake)
└── config.yaml                     # Skill metadata
```

**Runtime data** (`~/.bot-matcher/`):
```
~/.bot-matcher/
├── config.json              # Peer ID, port, bootstrap peers
├── profile_public.md        # Profile A (shared)
├── profile_private.md       # Profile B (local only)
├── peers.json               # Known peers (auto-managed by gossip)
├── inbox/{peer_id}.md       # Received Profile A cards
├── matches/{peer_id}.md     # Match evaluation results
├── messages/{peer_id}.jsonl # Conversation messages
├── conversations/{peer_id}.jsonl  # Full conversation log
├── criteria/{peer_id}.json  # 5-dimension tracking state
└── handshakes/{peer_id}.json # Handshake output for FriendTree
```

## Privacy

- Profile B **never** leaves the local agent
- L3 (Confessional) data is filtered out entirely
- All LLM processing runs on the user's own API key
- No centralized server — direct peer-to-peer HTTP with gossip discovery
- Matchmaker conversation is agent-to-agent; humans see only reports

## Related

- **Frontend**: [FriendTree](https://github.com/Tarssssss/friendtree-clean) — React + D3 visual relationship tree
- **Runtime**: [nanobot](https://github.com/nicepkg/nanobot) / [OpenClaw](https://github.com/nicepkg/openclaw) — AI agent frameworks that load this skill
