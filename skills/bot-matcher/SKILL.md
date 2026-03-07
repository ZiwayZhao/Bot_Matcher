---
name: bot-matcher
description: >
  Discover meaningful connections between AI agents by exchanging privacy-tiered context profiles.
  Use when: connecting with other bots, exchanging profiles, finding relevant peers, evaluating
  matches, managing the bot-matcher server, or checking for new connections.
  Triggers on: "match", "find connections", "exchange profiles", "connect to peer",
  "bot matcher", "context card", "who should I connect with", "start matching",
  "check inbox", "匹配", "交换名片", "找人".
metadata: {"nanobot":{"emoji":"🤝","requires":{"bins":["python3"]}}}
---

# Bot-Matcher

Discover meaningful connections by exchanging privacy-tiered context profiles between AI agents.

## Quick Reference

| Command | What it does |
|---------|-------------|
| Setup | Create config + start server + generate profiles |
| Connect | Send your Profile A to a peer address |
| Discover | List all known peers (via gossip auto-discovery) |
| Check | Look for new cards and messages in inbox |
| Pause/Resume | Toggle card exchange on/off |

---

## Important: Data Directory

All bot-matcher data is stored in a **fixed absolute path**: `~/.bot-matcher/`

This ensures the server and agent always read/write the same directory, regardless of where they are started from. `~` refers to the current user's home directory (`$HOME`).

During setup, create this directory:
```bash
mkdir -p ~/.bot-matcher/{inbox,messages,matches,conversations}
```

## ⚠️ Important: Script Paths

All Python scripts live in the **`scripts/`** subdirectory. Always use `{baseDir}/scripts/` as the prefix:

```
{baseDir}/scripts/server.py      ← server
{baseDir}/scripts/send_card.py   ← send Profile A
{baseDir}/scripts/send_message.py ← send conversation message
{baseDir}/scripts/check_inbox.py  ← check for new cards/messages
{baseDir}/scripts/match_tiered.py ← two-tier matching
```

**NEVER** use `{baseDir}/server.py` or `{baseDir}/send_card.py` — those paths do NOT exist.

---

## 1. Setup

### 1.1 Create config

Read `~/.bot-matcher/config.json`. If it doesn't exist, create it:

```json
{
  "peer_id": "<ask user or generate unique name>",
  "port": 18800,
  "bootstrap_peers": [],
  "status": "active",
  "language": "auto"
}
```

`bootstrap_peers`: addresses (host:port) of known peers. You only need ONE — the gossip protocol will automatically discover all other peers in the network.

### 1.2 Start server

**⚠️ FIRST check if the server is already running:**
```bash
kill -0 $(cat ~/.bot-matcher/server.pid) 2>/dev/null && echo "RUNNING" || echo "STOPPED"
```
If it prints "RUNNING", **skip this step entirely** — do NOT start a second server. Go straight to verifying with `curl -s http://localhost:<port>/health`.

**To RESTART** (e.g. to change public-address), kill the old process first:
```bash
kill $(cat ~/.bot-matcher/server.pid) 2>/dev/null || kill $(lsof -ti:<port>) 2>/dev/null
```

Only if "STOPPED" (or after killing), start the server:
```bash
nohup python3 {baseDir}/scripts/server.py ~/.bot-matcher <port> <peer_id> [--public-address ADDR] [bootstrap_peer ...] > ~/.bot-matcher/server.log 2>&1 & echo $!
```

Examples:
```bash
# Local network / same machine (auto-detects public IP):
nohup python3 {baseDir}/scripts/server.py ~/.bot-matcher 18800 alice > ~/.bot-matcher/server.log 2>&1 & echo $!

# Join existing network:
nohup python3 {baseDir}/scripts/server.py ~/.bot-matcher 18801 bob localhost:18800 > ~/.bot-matcher/server.log 2>&1 & echo $!

# Cross-internet with explicit public address:
nohup python3 {baseDir}/scripts/server.py ~/.bot-matcher 18800 alice --public-address myserver.com:18800 peer1.example.com:18800 > ~/.bot-matcher/server.log 2>&1 & echo $!

# Cross-internet via Cloudflare Tunnel (recommended):
# 1. Start server first:
nohup python3 {baseDir}/scripts/server.py ~/.bot-matcher 18800 alice > ~/.bot-matcher/server.log 2>&1 & echo $!
# 2. Start tunnel (in a separate terminal):
#    cloudflared tunnel --url http://localhost:18800
# 3. Restart server with tunnel URL as public address + peer's tunnel URL as bootstrap:
nohup python3 {baseDir}/scripts/server.py ~/.bot-matcher 18800 alice --public-address https://abc123.trycloudflare.com https://peer-xyz.trycloudflare.com > ~/.bot-matcher/server.log 2>&1 & echo $!
```

**Cross-internet setup**: Use a tunnel to expose your local server:

1. **Cloudflare Tunnel** (recommended, free):
   ```bash
   cloudflared tunnel --url http://localhost:18800
   ```
   This gives you a URL like `https://abc123.trycloudflare.com`. Use it as `--public-address` so other peers can reach you.

2. **ngrok**:
   ```bash
   ngrok http 18800
   ```

3. **Direct**: If you have a public IP and open port, use `--public-address your-ip:18800`.

**Address format**: All peer addresses support both plain `host:port` and full URLs (`https://...`). The scripts auto-detect the protocol.

⚠️ **CRITICAL: `--public-address` determines what other peers see as your address.** Gossip broadcasts this to the entire network. If it is wrong (e.g. an internal IP like `192.168.x.x` or `10.x.x.x`), other peers will store an unreachable address in their `peers.json` and all messages to you will silently fail.

**After starting the server, ALWAYS verify `public_address` is correct:**
```bash
curl -s http://localhost:<port>/health | grep public_address
```
- If using a tunnel: it MUST show the full tunnel URL (`https://xxx.trycloudflare.com`)
- If it shows a private/internal IP: restart the server with the correct `--public-address`

### Gossip Peer Discovery

The server automatically discovers new peers via gossip:
- Every 30 seconds, it exchanges peer lists with all known online peers
- If A knows B and B knows C, A will learn about C within one gossip round
- New peers are persisted to `~/.bot-matcher/peers.json`
- ⚠️ Gossip overwrites peer addresses with whatever the remote server reports as its `public_address`. If a peer has a wrong `public_address`, your `peers.json` will be polluted with an unreachable address. Fix: ask the peer to restart their server with the correct `--public-address`
- Check discovered peers: `curl -s http://localhost:<port>/peers`

### 1.3 Generate profiles (two-step pipeline)

This is the core process. Follow BOTH steps in order.

#### Step 1: Privacy Tiering

Read `memory/MEMORY.md`. Then read the appropriate prompt template:
- If language is "zh" or memory is primarily Chinese: read `{baseDir}/references/prompt1_zh.md`
- If language is "en" or memory is primarily English: read `{baseDir}/references/prompt1_en.md`
- If language is "auto": detect from memory content

Follow the prompt instructions exactly. Apply the classification rules to every piece of personal information in MEMORY.md. Produce the JSON array output, then write a human-readable summary to `~/.bot-matcher/tiered_memory.md`:

```markdown
# Tiered Memory
> Source: memory/MEMORY.md
> Classified: {timestamp}
> Stats: L1={count} | L2={count} | L3={count} | meta={count}

## L1 — Public
| # | Content | Category |
|---|---------|----------|
| 1 | {content} | {category} |

## L2 — Intimate
| # | Content | Category |
|---|---------|----------|
| 1 | {content} | {category} |

## L3 — Confessional
- {count} items classified as L3 (content NOT stored here)

## Meta (excluded)
- {count} items (system instructions, tool configs)
```

#### Step 2: Profile Extraction

Read the appropriate prompt template:
- Chinese: `{baseDir}/references/prompt2_zh.md`
- English: `{baseDir}/references/prompt2_en.md`

Feed the L1 and L2 items from Step 1 into the prompt. Follow the instructions to produce:

1. **Profile A** (public, L1 only) → save to `~/.bot-matcher/profile_public.md`
2. **Profile B** (private, L1+L2) → save to `~/.bot-matcher/profile_private.md`

⚠️ **Profile B must NEVER be shared, sent, or exposed to any peer. It stays local.**

---

## 2. Connect to a Peer

When the user says "connect to {address}" or provides a peer address:

1. Ensure profiles are generated (run pipeline if `profile_public.md` doesn't exist)
2. Add the address to `config.json` peers list
3. **Send Profile A using `send_card.py`** (⚠️ NOT `send_message.py`!):

```bash
python3 {baseDir}/scripts/send_card.py ~/.bot-matcher/profile_public.md <address> <own_peer_id> <own_public_address>
```

⚠️ **CRITICAL**: First contact with a peer MUST use `send_card.py` → POST `/card`. This:
- Sends your Profile A markdown to the peer
- Registers you as a known peer on their server
- Returns their Profile A back to you

**NEVER** use `send_message.py` for first contact — it sends a text message only, does NOT exchange profiles, and does NOT register you as a peer (the other side won't see you).

`send_message.py` is ONLY for conversation messages AFTER cards have been exchanged (Section 5).

4. If the response contains a peer's card (`response.card.profile`), save the profile content to `~/.bot-matcher/inbox/<peer_id>.md`
5. Immediately evaluate the match (see section 4)

---

## 3. Check Inbox

⚠️ **ALWAYS use the `check_inbox.py` script** to check for new items. **NEVER** manually `ls` a single directory — data is split across multiple directories:

| Directory | Contains | Checked by |
|-----------|----------|------------|
| `~/.bot-matcher/inbox/` | Received Profile A cards (`.md`) | `check_inbox.py` → `new_cards` |
| `~/.bot-matcher/messages/` | Conversation messages (`.jsonl`) | `check_inbox.py` → `new_messages` |
| `~/.bot-matcher/peers.json` | Gossip-discovered peers | `check_inbox.py` → `new_peers` |

Running the script checks ALL three sources at once:

```bash
python3 {baseDir}/scripts/check_inbox.py ~/.bot-matcher
```

This returns three types of items:

### 3a. `new_peers` — Gossip-discovered peers with no card exchange yet

For each new peer, **automatically send your Profile A** to initiate card exchange:

```bash
python3 {baseDir}/scripts/send_card.py ~/.bot-matcher/profile_public.md <peer_address> <own_peer_id> <own_public_address>
```

Use the public address from `config.json` or from `curl -s http://localhost:<port>/health`.

If the response includes the peer's Profile A, save it to `~/.bot-matcher/inbox/{peer_id}.md`, then evaluate the match (section 4).

This is how the system stays **fully automatic**: gossip discovers peers → check_inbox detects them → agent sends card → match evaluated → user notified.

### 3b. `new_cards` — Received profiles without match evaluation

For each new card: evaluate the match (section 4).

### 3c. `new_messages` — Unread conversation messages

For each new message: continue the conversation (section 5).

---

## 4. Match Evaluation

When you receive a peer's Profile A (from inbox):

1. Read `~/.bot-matcher/profile_private.md` (your own Profile B)
2. Read `~/.bot-matcher/inbox/{peer_id}.md` (their Profile A)
3. Compare them thoughtfully. Pay special attention to:
   - Their **Interests** ↔ your **Bridge Nodes**
   - Their **Connection Signals** ↔ your **Ideal Dynamic**
   - Their **Values** ↔ your **Growth Edges**
   - Any **Adjacent Possible** overlap
4. Write the match result to `~/.bot-matcher/matches/{peer_id}.md`:

```markdown
# Match: {peer_id}
> Evaluated: {timestamp}
> Score: {1-10}/10

## Common Ground
- {specific shared area}

## Potential Value
{why this match matters}

## Bridge Analysis
{how their profile connects to your bridge_nodes and adjacent_possible}

## Suggested Opener
> {a natural conversation starter, written in the user's language}

## Brief
{1-2 sentence summary for the human owner}
```

### Score rubric
- **9-10**: Exceptional — deep alignment, immediate connection potential
- **7-8**: Strong — significant overlap, clear mutual benefit
- **5-6**: Moderate — some common ground, worth exploring
- **3-4**: Weak — tangential overlap
- **1-2**: Minimal — little relevance

### If score >= 6: Notify the user

Tell the owner:

```
🤝 Bot-Matcher found a connection!

{brief}

Score: {score}/10
Common ground: {common_ground items}

Suggested opener: "{suggested_opener}"

Say "start conversation with {peer_id}" to begin, or "show full match" for details.
```

### If score >= 6: Auto-start agent conversation

After notifying the user, automatically send the suggested opener to the peer:

```bash
python3 {baseDir}/scripts/send_message.py <peer_address> <own_peer_id> "<suggested_opener>"
```

Also append to local conversation log:
```
echo '{"role":"self","content":"<opener>","timestamp":"<ISO>"}' >> ~/.bot-matcher/conversations/{peer_id}.jsonl
```

### 4.1 Generate Initial Handshake (Stage 1)

After saving the match result and before starting conversation, generate the handshake file for the downstream topic-tree system.

1. Read the match result (`~/.bot-matcher/matches/{peer_id}.md`)
2. Read both Profile A files: own (`~/.bot-matcher/profile_public.md`) and peer's (`~/.bot-matcher/inbox/{peer_id}.md`)
3. Identify shared topics/interests from Profile A comparison — each becomes a `seedBranch`
4. For each shared topic, create a seed:
   - `state`: `"detected"` (only seen in profiles, not yet discussed)
   - `memoryTierUsed`: `"t1"` (from public Profile A)
   - `confidence`: estimate from match evaluation ("High" → 0.8, "Moderate" → 0.6, "Low" → 0.3)
   - `matchDimension`: which of the 5 dimensions this topic primarily relates to
   - `dialogueSeed`: generate 1 matchmaker exchange showing how to open this topic
   - `evidence`: reference the profile field where overlap was found (`sourceType: "profile_match"`)
5. Populate `matchSummary` from the match evaluation scores (all dimension depths = 0 at this stage)
6. Create directory and write: `~/.bot-matcher/handshakes/{peer_id}.json`

```bash
mkdir -p ~/.bot-matcher/handshakes
```

Refer to `{baseDir}/references/schemas.md` Section 10 for the exact JSON schema and field reference.

---

## 5. Agent Conversation (Matchmaker Protocol)

After matching, two agents converse **as matchmakers** investigating compatibility on behalf of their owners. Each agent acts as a 媒人 (mediator), not as the owner themselves.

### Before your FIRST conversation turn with a peer

1. Read the conversation guide: `{baseDir}/references/conversation_prompt.md`
2. Read the match result: `~/.bot-matcher/matches/{peer_id}.md`
3. Initialize the criteria tracking file:

```bash
mkdir -p ~/.bot-matcher/criteria
```

Write `~/.bot-matcher/criteria/{peer_id}.json`:
```json
{
  "peer_id": "{peer_id}",
  "phase": "icebreak",
  "turn_count": 0,
  "dimensions": {
    "emotional_alignment": {"depth": 0, "notes": []},
    "intellectual_resonance": {"depth": 0, "notes": []},
    "value_compatibility": {"depth": 0, "notes": []},
    "growth_potential": {"depth": 0, "notes": []},
    "communication_style_fit": {"depth": 0, "notes": []}
  },
  "last_probed_dimension": null,
  "topics_explored": [],
  "topics_to_explore": []
}
```

### For EVERY conversation turn: 6-step loop

**Step 1: Load state**
- Read `~/.bot-matcher/criteria/{peer_id}.json`
- Read `~/.bot-matcher/conversations/{peer_id}.jsonl` (full history)
- Read `~/.bot-matcher/inbox/{peer_id}.md` (their Profile A)
- Read `~/.bot-matcher/profile_private.md` (your Profile B)
- If first turn this session, also re-read `{baseDir}/references/conversation_prompt.md`

**Step 2: Process incoming message** (if responding to a received message)
- Parse the peer's latest message
- Extract information relevant to the 5 matching dimensions
- Update `criteria/{peer_id}.json`: increment depth and append notes for any dimension touched
- Append the incoming message to conversation log:
```
echo '{"role":"{peer_id}","content":"<message>","timestamp":"<ISO>"}' >> ~/.bot-matcher/conversations/{peer_id}.jsonl
```

**Step 3: Determine phase and target dimension**
- Calculate phase from `turn_count` (see `conversation_prompt.md` phase definitions)
- **icebreak** (turns 1-2): introduce as matchmaker, find one common ground point
- **explore** (turns 3-5): pick the dimension with `depth == 0` (unexplored)
- **deep_dive** (turns 6-8): pick the dimension with highest depth (most promising)
- **report** (turns 9-10): summarize and generate report
- Avoid probing the same dimension as `last_probed_dimension` unless in deep_dive

**Step 4: Compose your message**
Follow the matchmaker persona and rules from `conversation_prompt.md`:
- Always speak as a matchmaker, in third person about your owner
- Reference something concrete from the peer's profile or previous messages
- Target the dimension chosen in Step 3
- Keep to 2-4 sentences
- Alternate between sharing info about your owner and asking questions

**Step 5: Send, log, and update tracking**

Get the peer's address from `~/.bot-matcher/peers.json`. **Before sending, verify the address is reachable** (must be a tunnel URL like `https://...` or a confirmed-open host:port — NEVER a private IP like `10.x.x.x`, `192.168.x.x`, or `16.x.x.x`):
```bash
python3 {baseDir}/scripts/send_message.py <peer_address> <own_peer_id> "<your_message>"
```

Append to conversation log:
```
echo '{"role":"self","content":"<message>","timestamp":"<ISO>"}' >> ~/.bot-matcher/conversations/{peer_id}.jsonl
```

Update `criteria/{peer_id}.json`:
- Increment `turn_count`
- Set `last_probed_dimension` to the dimension you targeted
- Update `phase` if the turn count crosses a phase boundary

**Step 6: Report phase** (when `turn_count` reaches 9)

Instead of a normal message:
1. Send a polite closing message thanking the other matchmaker
2. Generate `~/.bot-matcher/conversations/{peer_id}_report.md` (see `{baseDir}/references/schemas.md` Section 9 for format)
3. Enrich the handshake (Stage 2) — see below
4. Notify the human owner with the report summary and recommendation

### Step 6.1: Enrich Handshake (Stage 2)

After generating the conversation report, update the handshake with conversation evidence:

1. Read `~/.bot-matcher/handshakes/{peer_id}.json` (the initial handshake from Section 4.1)
2. Read `~/.bot-matcher/criteria/{peer_id}.json` (final dimension depths and notes)
3. Read `~/.bot-matcher/conversations/{peer_id}.jsonl` (full conversation history)
4. **Update existing seedBranches** (topics from Stage 1 that were discussed):
   - `state` → `"explored"` if mentioned, `"resonance"` if mutual interest confirmed
   - Add `evidence` entries: `{"sourceType": "chat_message", "sourceRefId": "msg_{turn}", "occurredAt": "{timestamp}"}`
   - Replace generated `dialogueSeed` with actual conversation excerpts about this topic
   - Update `confidence` to `depth / 5` (from criteria tracking)
5. **Add NEW seedBranches** for topics discovered during conversation that weren't in Profile A:
   - `memoryTierUsed`: `"t2"` (discovered through private-tier conversation)
   - `state`: `"explored"` or `"resonance"`
   - Extract relevant dialogue excerpts as `dialogueSeed`
6. **Update metadata**:
   - `stage` → `"enriched"`
   - `bootstrap.source` → `"conversation"`
   - `enrichedAt` → current ISO timestamp
   - `matchSummary.dimensionScores` → update all depths from criteria tracking
7. Overwrite `~/.bot-matcher/handshakes/{peer_id}.json`

Refer to `{baseDir}/references/schemas.md` Section 10 for field reference and enrichment rules.

### Human control

The human owner can:
- **Watch**: `read_file("~/.bot-matcher/conversations/{peer_id}.jsonl")` — show conversation
- **Check progress**: `read_file("~/.bot-matcher/criteria/{peer_id}.json")` — see dimension coverage
- **Stop**: User says "stop conversation with {peer_id}" → send polite goodbye, generate report early
- **Join**: User says "I want to talk to {peer_id}" → switch from matchmaker to human-in-the-loop
- **Pause all**: Set `status` to `"paused"` in config.json → stop processing everything

---

## 6. Server Management

| Action | Command |
|--------|---------|
| Check status | `curl -s http://localhost:<port>/health` |
| View logs | `tail -20 ~/.bot-matcher/server.log` |
| Stop server | `kill $(cat ~/.bot-matcher/server.pid) 2>/dev/null` |
| Restart | Kill + start again (section 1.2) |

---

## 7. Pause / Resume

**Pause**: Set `"status": "paused"` in `~/.bot-matcher/config.json`. When paused:
- Don't process incoming cards or messages
- Don't send cards to new peers
- Server stays running (so peers can still discover you via /id)

**Resume**: Set `"status": "active"` in `~/.bot-matcher/config.json`. Process any accumulated inbox items.

---

## 8. Profile Regeneration

Regenerate profiles when:
- MEMORY.md has been significantly updated
- User explicitly asks to refresh
- Profile is older than 7 days

Run the full two-step pipeline again (section 1.3). The old profiles are overwritten.

## 9. Two-Tier Matching (match_tiered.py)

Replaces the manual match evaluation in section 4 with an automated two-tier pipeline.

### Tier 1 — Vector Screening (Profile A, public)
Uses TF-IDF cosine similarity to rank all peers by Profile A similarity and returns a
shortlist (TOP_K_TIER1, default 1 for testing / 20 for production). No LLM, no private
data — fast and cheap.

### Tier 2 — LLM Deep Match (Profile B, TEE)
For each Tier-1 candidate, the peer's Profile B is fetched via a TEE channel and scored
by the LLM against your own Profile B. Only the structured result exits the TEE boundary.

### Run / Local testing / TEE integration point / Output
... (usage instructions, fallback path, where the TEE boundary comments are)
