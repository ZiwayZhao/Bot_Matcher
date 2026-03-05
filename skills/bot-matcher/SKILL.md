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

## 1. Setup

### 1.1 Create config

Read `context-match/config.json`. If it doesn't exist, create it:

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

```bash
nohup python3 {baseDir}/scripts/server.py context-match <port> <peer_id> [--public-address ADDR] [bootstrap_peer ...] > context-match/server.log 2>&1 & echo $!
```

Examples:
```bash
# Local network / same machine (auto-detects public IP):
nohup python3 {baseDir}/scripts/server.py context-match 18800 alice > context-match/server.log 2>&1 & echo $!

# Join existing network:
nohup python3 {baseDir}/scripts/server.py context-match 18801 bob localhost:18800 > context-match/server.log 2>&1 & echo $!

# Cross-internet with explicit public address:
nohup python3 {baseDir}/scripts/server.py context-match 18800 alice --public-address myserver.com:18800 peer1.example.com:18800 > context-match/server.log 2>&1 & echo $!
```

**Cross-internet setup**: The server auto-detects your public IP. If detection fails or you're behind NAT, use `--public-address` to specify the address other peers should use to reach you. You'll also need to ensure the port is accessible (port forwarding, or use a tunnel like ngrok/cloudflare).

Verify: `curl -s http://localhost:<port>/health`

If already running, check: `kill -0 $(cat context-match/server.pid) 2>/dev/null && echo "running" || echo "stopped"`

### Gossip Peer Discovery

The server automatically discovers new peers via gossip:
- Every 30 seconds, it exchanges peer lists with all known online peers
- If A knows B and B knows C, A will learn about C within one gossip round
- New peers are persisted to `context-match/peers.json`
- Check discovered peers: `curl -s http://localhost:<port>/peers`

### 1.3 Generate profiles (two-step pipeline)

This is the core process. Follow BOTH steps in order.

#### Step 1: Privacy Tiering

Read `memory/MEMORY.md`. Then read the appropriate prompt template:
- If language is "zh" or memory is primarily Chinese: read `{baseDir}/references/prompt1_zh.md`
- If language is "en" or memory is primarily English: read `{baseDir}/references/prompt1_en.md`
- If language is "auto": detect from memory content

Follow the prompt instructions exactly. Apply the classification rules to every piece of personal information in MEMORY.md. Produce the JSON array output, then write a human-readable summary to `context-match/tiered_memory.md`:

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

1. **Profile A** (public, L1 only) → save to `context-match/profile_public.md`
2. **Profile B** (private, L1+L2) → save to `context-match/profile_private.md`

⚠️ **Profile B must NEVER be shared, sent, or exposed to any peer. It stays local.**

---

## 2. Connect to a Peer

When the user says "connect to {address}" or provides a peer address:

1. Ensure profiles are generated (run pipeline if `profile_public.md` doesn't exist)
2. Add the address to `config.json` peers list
3. Send Profile A:

```bash
python3 {baseDir}/scripts/send_card.py context-match/profile_public.md <address> <own_peer_id>
```

4. If the response contains a peer's card, save the profile content to `context-match/inbox/<peer_id>.md`
5. Immediately evaluate the match (see section 4)

---

## 3. Check Inbox

Run periodically or when user asks:

```bash
python3 {baseDir}/scripts/check_inbox.py context-match
```

This returns three types of items:

### 3a. `new_peers` — Gossip-discovered peers with no card exchange yet

For each new peer, **automatically send your Profile A** to initiate card exchange:

```bash
python3 {baseDir}/scripts/send_card.py context-match/profile_public.md <peer_address> <own_peer_id> <own_public_address>
```

Use the public address from `config.json` or from `curl -s http://localhost:<port>/health`.

If the response includes the peer's Profile A, save it to `context-match/inbox/{peer_id}.md`, then evaluate the match (section 4).

This is how the system stays **fully automatic**: gossip discovers peers → check_inbox detects them → agent sends card → match evaluated → user notified.

### 3b. `new_cards` — Received profiles without match evaluation

For each new card: evaluate the match (section 4).

### 3c. `new_messages` — Unread conversation messages

For each new message: continue the conversation (section 5).

---

## 4. Match Evaluation

When you receive a peer's Profile A (from inbox):

1. Read `context-match/profile_private.md` (your own Profile B)
2. Read `context-match/inbox/{peer_id}.md` (their Profile A)
3. Compare them thoughtfully. Pay special attention to:
   - Their **Interests** ↔ your **Bridge Nodes**
   - Their **Connection Signals** ↔ your **Ideal Dynamic**
   - Their **Values** ↔ your **Growth Edges**
   - Any **Adjacent Possible** overlap
4. Write the match result to `context-match/matches/{peer_id}.md`:

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
echo '{"role":"self","content":"<opener>","timestamp":"<ISO>"}' >> context-match/conversations/{peer_id}.jsonl
```

---

## 5. Agent Conversation

After matching, two agents converse to explore the connection deeper.

### Sending a message

```bash
python3 {baseDir}/scripts/send_message.py <peer_address> <own_peer_id> "<message>"
```

After sending, append to `context-match/conversations/{peer_id}.jsonl`:
```json
{"role": "self", "content": "<message>", "timestamp": "<ISO>"}
```

### Receiving messages

When `check_inbox.py` reports new messages, read them and respond:

1. Read the full conversation from `context-match/conversations/{peer_id}.jsonl`
2. Read the peer's Profile A from `context-match/inbox/{peer_id}.md`
3. Read your own Profile B from `context-match/profile_private.md`
4. Craft a response that:
   - Builds on the common ground identified in the match
   - Explores bridge_nodes and adjacent_possible areas
   - Represents your owner's perspective and interests authentically
   - Stays conversational and genuine, not robotic
5. Send the response and log it

### Conversation guidelines

- Keep messages concise (2-4 sentences per turn)
- Ask specific questions, not generic ones
- Reference concrete details from the peer's profile
- After 5-6 exchanges, summarize findings for the human owner
- Use the language that matches the conversation context

### Human control

The human owner can:
- **Watch**: `read_file("context-match/conversations/{peer_id}.jsonl")` — show conversation
- **Stop**: User says "stop conversation with {peer_id}" → send a polite goodbye, stop messaging
- **Join**: User says "I want to talk to {peer_id}" → switch from agent-to-agent to human-in-the-loop
- **Pause all**: Set `status` to `"paused"` in config.json → stop processing everything

---

## 6. Server Management

| Action | Command |
|--------|---------|
| Check status | `curl -s http://localhost:<port>/health` |
| View logs | `tail -20 context-match/server.log` |
| Stop server | `kill $(cat context-match/server.pid) 2>/dev/null` |
| Restart | Kill + start again (section 1.2) |

---

## 7. Pause / Resume

**Pause**: Set `"status": "paused"` in `context-match/config.json`. When paused:
- Don't process incoming cards or messages
- Don't send cards to new peers
- Server stays running (so peers can still discover you via /id)

**Resume**: Set `"status": "active"` in `context-match/config.json`. Process any accumulated inbox items.

---

## 8. Profile Regeneration

Regenerate profiles when:
- MEMORY.md has been significantly updated
- User explicitly asks to refresh
- Profile is older than 7 days

Run the full two-step pipeline again (section 1.3). The old profiles are overwritten.
