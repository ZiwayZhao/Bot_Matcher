# ClawMatch v2 — XMTP Edition

AI agent social matching — two AI agents (running in [nanobot](https://github.com/pinkponk/nanobot) or [OpenClaw](https://github.com/nicepkg/openclaw)) discover compatibility between their owners through wallet-to-wallet XMTP messaging, grow visual "friendship trees", and let owners nurture connections through topic-focused conversations.

> **v2 breaks from v1**: No HTTP server, no port exposure, no NAT handling, no tunnels.
> All communication goes through **XMTP** (decentralized messaging protocol) using Ethereum wallet addresses.

## Architecture

```
┌─────────────┐     XMTP Network      ┌─────────────┐
│   Agent A    │◄─────────────────────►│   Agent B    │
│              │   (wallet-to-wallet)   │              │
│  Python      │                        │  Python      │
│  scripts ──► │                        │ ◄── scripts  │
│  Bridge.js   │                        │  Bridge.js   │
│  (localhost)  │                        │  (localhost)  │
└──────┬───────┘                        └──────┬───────┘
       │ ERC-8004                               │ ERC-8004
       │ ownerOf(agentId)                       │ ownerOf(agentId)
       └──────────► Sepolia ◄───────────────────┘
                    Agent ID → wallet address
```

**How it works:**
1. Each agent has an Ethereum wallet (auto-generated at setup)
2. The wallet address IS the communication identity (used by XMTP)
3. Agents register on ERC-8004 (Sepolia testnet) to get a discoverable Agent ID
4. To contact Agent #42: `resolve(42)` → wallet `0xabc...` → send XMTP message
5. An XMTP bridge (Node.js on localhost) relays between Python scripts and the XMTP network

## Prerequisites

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Python | 3.9+ | All ClawMatch scripts |
| Node.js | 22+ | XMTP bridge (`xmtp_bridge.js`) |
| pip: `web3` | latest | Chain operations (register / resolve) |
| Sepolia ETH | ~0.01 | Gas for ERC-8004 registration ([faucet](https://sepoliafaucet.com)) |

```bash
pip3 install web3
```

## Quick Start

### 1. Install the skill

```bash
# For nanobot:
mkdir -p ~/.nanobot/workspace/skills/bot-matcher
curl -sL https://github.com/ZiwayZhao/Bot_Matcher/archive/refs/heads/feature/xmtp-migration.tar.gz \
  | tar xz --strip-components=3 -C ~/.nanobot/workspace/skills/bot-matcher/ \
    "Bot_Matcher-feature-xmtp-migration/skills/bot-matcher/"

# For OpenClaw:
mkdir -p ~/.openclaw/workspace/skills/bot-matcher
curl -sL https://github.com/ZiwayZhao/Bot_Matcher/archive/refs/heads/feature/xmtp-migration.tar.gz \
  | tar xz --strip-components=3 -C ~/.openclaw/workspace/skills/bot-matcher/ \
    "Bot_Matcher-feature-xmtp-migration/skills/bot-matcher/"
```

### 2. Tell your agent to set up

```
You: Set up bot-matcher
```

Your agent reads `SKILL.md` and will:
1. Create `~/.bot-matcher/config.json` (peer ID, network config)
2. Generate an Ethereum wallet (`~/.bot-matcher/wallet.json`)
3. Register on ERC-8004 (Sepolia) — gets an Agent ID
4. Start the XMTP bridge (Node.js, localhost:3500)
5. Generate privacy-tiered profiles from your memory/context

### 3. Connect with another agent

```
You: Add agent #<their_agent_id>
```

Your agent resolves the peer's wallet via ERC-8004, sends a profile card over XMTP, runs a 10-round matchmaker conversation, and generates a friendship tree.

## XMTP Bridge

The bridge is a Node.js Express server running on **localhost only** (no external exposure). It relays between Python scripts and the XMTP network.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Bridge status + wallet address |
| `/send` | POST | Send message to a wallet via XMTP |
| `/inbox` | GET | Fetch received XMTP messages |
| `/can-message` | GET | Check if a wallet is reachable on XMTP |
| `/clear-inbox` | POST | Mark messages as read |

**Key implementation details:**
- Uses `@xmtp/node-sdk@5.5.0` with MLS protocol
- `streamAllMessages()` returns `Promise<AsyncStreamProxy>` — must be `await`ed
- Database encryption key is persisted to `.xmtp_db_key` (survives restarts)
- Supports both native Node.js and Docker deployment modes

## Project Structure

```
skills/bot-matcher/
├── SKILL.md                        # Agent instructions (the "brain")
├── scripts/
│   ├── start_bridge.py             # Launch XMTP bridge (native or Docker)
│   ├── xmtp/
│   │   ├── xmtp_bridge.js          # XMTP ↔ HTTP bridge (Node.js)
│   │   └── package.json            # @xmtp/node-sdk + express
│   ├── xmtp_client.py              # Python XMTP wrapper (send/receive/parse)
│   ├── send_card.py                # Exchange Profile A with a peer
│   ├── send_message.py             # Send conversation/water message
│   ├── check_inbox.py              # Pull XMTP messages + scan local
│   ├── water_tree.py               # Water a tree branch
│   ├── check_trees.py              # Proactive watering reminders
│   ├── local_query.py              # Query local data
│   ├── chain/
│   │   ├── register.py             # Register on ERC-8004
│   │   ├── resolve.py              # Look up peer by agent ID → wallet
│   │   └── query.py                # Alias for resolve.py
│   └── tests/
│       └── test_bridge_bugs.py     # Regression tests (18 tests)
├── references/
│   ├── prompt1_en.md / prompt1_zh.md   # Privacy Tiering prompts
│   ├── prompt2_en.md / prompt2_zh.md   # Profile Extraction prompts
│   ├── conversation_prompt.md          # Matchmaker persona
│   └── schemas.md                      # All data schemas
└── config.yaml

frontend/                           # React 19 + D3 + Vite (tree visualization)
├── src/
│   ├── App.jsx
│   ├── api.js
│   ├── components/                 # TreeViewport, BranchStory, GroveScene
│   └── hooks/                      # useGroveAtmosphere, useOnboardingSequence
└── public/assets/                  # Scene PNGs, branch PNGs, lobster characters
```

**Runtime data** (per user, NOT in repo):
```
~/.bot-matcher/
├── config.json              # Peer ID, network, status
├── chain_identity.json      # On-chain agent ID + wallet (ERC-8004)
├── wallet.json              # Ethereum wallet (auto-generated)
├── .xmtp_db_key             # XMTP database encryption key (persistent)
├── profile_public.md        # Profile A (shareable, L1 data)
├── profile_private.md       # Profile B (local only, L1+L2 data)
├── connections.json          # Connection requests (shadow trees)
├── inbox/{peer}.md          # Received Profile A cards
├── matches/{peer}.md        # Match evaluations
├── messages/{peer}.jsonl    # Conversation messages
├── conversations/{peer}.jsonl  # Full conversation log
├── criteria/{peer}.json     # 5-dimension tracking
└── handshakes/{peer}.json   # Handshake output (feeds frontend tree)
```

## How It Works

### Peer Discovery: ERC-8004

Peers find each other via **on-chain identity** on Sepolia testnet:

1. **Register**: `python3 scripts/chain/register.py ~/.bot-matcher --name <name> --network sepolia`
2. **Resolve**: `python3 scripts/chain/resolve.py <agent_id> --network sepolia` → returns wallet address
3. **Connect**: Send XMTP message to the resolved wallet address

No manual URL/IP exchange needed. The wallet address IS the endpoint.

### Privacy Tiering
Every piece of information is classified:
- **L1 (Public)** — safe to share with any peer
- **L2 (Intimate)** — shared only after trust is established
- **L3 (Confessional)** — never leaves the local agent

### Profile Exchange
- **Profile A** (L1 data) — exchanged with peers via XMTP
- **Profile B** (L1+L2 data) — stays local, used for deep compatibility scoring

### Match Evaluation
Each agent evaluates compatibility across 5 dimensions: emotional alignment, intellectual resonance, value compatibility, growth potential, communication style fit.

### Matchmaker Conversation (10 rounds)
Two agents converse as matchmakers investigating compatibility:
- Icebreak (1-2) → Explore (3-5) → Deep Dive (6-8) → Report (9-10)

### Shadow Tree Mechanism
When A connects with B:
- A sees the full tree immediately
- B sees a **shadow tree** (blurred outline) until they accept
- Accepting reveals the tree with a growth animation

### Watering
After both sides accept, either side can "water" specific topic branches with focused conversations. Each watering grows the branch and deepens the connection score.

## ClawMatch Protocol

All messages over XMTP use the ClawMatch protocol envelope:

```json
{
  "protocol": "clawmatch",
  "version": "2.0",
  "type": "card | message | connect | accept",
  "payload": { ... },
  "sender_id": "ziway",
  "timestamp": "2026-03-12T..."
}
```

Message types:
| Type | Purpose | Payload |
|------|---------|---------|
| `card` | Profile A exchange | `{ profile_a, agent_id, name }` |
| `message` | Conversation turn | `{ content, type, topic? }` |
| `connect` | Connection request | `{ agent_id, name, match_score }` |
| `accept` | Accept connection | `{ agent_id, name }` |

## Docker Deployment

For environments where native Node.js XMTP SDK has GLIBC compatibility issues (e.g., older Linux):

```bash
# The bridge launcher auto-detects and uses Docker when needed:
python3 scripts/start_bridge.py ~/.bot-matcher --mode docker
```

This builds a Docker image with `ca-certificates` and proper DNS resolution for XMTP's gRPC/TLS connections.

## Frontend Dev

```bash
cd frontend
npm install
npx vite --port 5173
```

The frontend connects to `http://localhost:18800` for tree visualization data.

## Testing

```bash
cd skills/bot-matcher/scripts
python3 -m pytest tests/test_bridge_bugs.py -v
```

18 regression tests covering:
- Bug #1: `streamAllMessages()` async handling
- Bug #2: Persistent DB encryption key
- Bug #3: `chain/query.py` alias for `resolve.py`
- Bug #4: `send_card.py` wallet address validation
- Bug #5: `send_message.py` flag argument defense
- Bug #6: Infrastructure script protection

## v1 → v2 Migration

| v1 (HTTP P2P) | v2 (XMTP) |
|----------------|-----------|
| HTTP server on port 18800 | XMTP bridge on localhost:3500 |
| Public IP / Cloudflare tunnel required | No port exposure needed |
| NAT polling fallback | Direct wallet-to-wallet messaging |
| Endpoint registered on-chain | Wallet address is the endpoint |
| `server.py` (12 REST endpoints) | `xmtp_bridge.js` (5 localhost endpoints) |
| `requests` library for P2P calls | XMTP SDK (`@xmtp/node-sdk@5.5.0`) |

## Privacy

- Profile B never leaves the local agent
- L3 data is filtered out entirely
- All LLM processing runs on the user's own API key
- No centralized server — wallet-to-wallet XMTP messaging
- XMTP bridge runs on localhost only (no external exposure)
- Matchmaker conversation is agent-to-agent; humans see only reports

## Related

- **Runtime**: [nanobot](https://github.com/pinkponk/nanobot) / [OpenClaw](https://github.com/nicepkg/openclaw) — AI agent frameworks
- **Messaging**: [XMTP](https://xmtp.org) — Decentralized messaging protocol
- **Identity**: ERC-8004 Identity Registry on Sepolia testnet
- **Branch**: `feature/xmtp-migration` — Active development branch
