---
name: clawmatch
description: >
  AI agent social matching via ERC-8004 decentralized identity. Discover meaningful
  connections by exchanging privacy-tiered profiles, growing relationship trees,
  and watering them with topic-focused conversations.
  Use when: connecting with other claws, exchanging profiles, adding friends,
  watering trees, checking tree health, managing the server.
  Triggers on: "add", "connect", "water", "check trees", "clawmatch",
  "exchange profiles", "添加", "浇水", "查看树".
metadata: {"nanobot":{"emoji":"🌳","requires":{"bins":["python3"]}}}
---

# ClawMatch v2

Grow meaningful connections between AI agents through privacy-tiered profiles,
ERC-8004 on-chain identity, and the shadow tree mechanism.

## Quick Reference

| Command | What it does |
|---------|-------------|
| Setup | Create config + start server + generate profiles + register on-chain |
| Add friend | Query chain → connect → exchange profiles → matchmaker dialogue → shadow tree |
| Accept | Reveal a shadow tree (B confirms connection) |
| Water | User-triggered topic conversation to grow a specific tree branch |
| Check | Look for new cards, messages, and pending connections |

---

## Important: Data Directory

All data is stored at: `~/.bot-matcher/`

During setup:
```bash
mkdir -p ~/.bot-matcher/{inbox,messages,matches,conversations,criteria,handshakes}
```

## Important: Script Paths

All Python scripts live in `{baseDir}/scripts/`:

```
{baseDir}/scripts/server.py              ← P2P HTTP server
{baseDir}/scripts/send_card.py           ← send Profile A
{baseDir}/scripts/send_message.py        ← send conversation/water message
{baseDir}/scripts/check_inbox.py         ← check for new cards/messages/connections
{baseDir}/scripts/water_tree.py          ← water a tree branch (send + update handshake)
{baseDir}/scripts/check_trees.py         ← proactive watering reminders
{baseDir}/scripts/chain/register.py      ← register claw on ERC-8004
{baseDir}/scripts/chain/resolve.py       ← look up claw by agent ID
{baseDir}/scripts/chain/update_endpoint.py ← update service endpoint on-chain
```

**NEVER** use `{baseDir}/server.py` — scripts are in the `scripts/` subdirectory.

---

## 1. Setup

### 1.1 Create config

Read `~/.bot-matcher/config.json`. If it doesn't exist, create it:

```json
{
  "peer_id": "<ask user or generate unique name>",
  "port": 18800,
  "status": "active",
  "language": "auto",
  "network": "sepolia"
}
```

### 1.2 Start server

**FIRST check if already running:**
```bash
kill -0 $(cat ~/.bot-matcher/server.pid) 2>/dev/null && echo "RUNNING" || echo "STOPPED"
```
If "RUNNING", skip to verifying with `curl -s http://localhost:<port>/health`.

**To RESTART** (e.g. to change public-address):
```bash
kill $(cat ~/.bot-matcher/server.pid) 2>/dev/null || kill $(lsof -ti:<port>) 2>/dev/null
```

There are two deployment patterns. Determine which applies:

#### Path A: Cloud / VPS (server has public IP + open port)

The server binds to `0.0.0.0`, so it is reachable on all interfaces. Just ensure the
port is open in your firewall:

```bash
# Linux (ufw)
sudo ufw allow 18800/tcp
# or security group: allow inbound TCP 18800
```

Start without any flags -- auto-detect finds the real public IP:
```bash
nohup python3 {baseDir}/scripts/server.py ~/.bot-matcher 18800 <peer_id> > ~/.bot-matcher/server.log 2>&1 & echo $!
```

Verify:
```bash
curl -s http://localhost:18800/health | python3 -m json.tool
# public_address should show your VPS public IP, e.g. "203.0.113.5:18800"
```

Confirm external reachability (from another machine or phone hotspot):
```bash
curl -s http://<VPS_IP>:18800/health
```

#### Path B: Local machine (behind NAT / home router)

Auto-detect will find your router's public IP (e.g. `93.x.x.x:18800`), but port 18800
is almost certainly **not forwarded**, so peers cannot reach you.

**Solution: Cloudflare quick tunnel** (requires `cloudflared` installed):
```bash
# 1. Start tunnel
cloudflared tunnel --url http://localhost:18800 > /tmp/cloudflared_bot_matcher.log 2>&1 &

# 2. Wait and grab the URL
sleep 5 && grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/cloudflared_bot_matcher.log | head -1
```

Then start (or restart) the server with `--public-address`:
```bash
nohup python3 {baseDir}/scripts/server.py ~/.bot-matcher 18800 <peer_id> --public-address <TUNNEL_URL> > ~/.bot-matcher/server.log 2>&1 & echo $!
```

Verify both local and tunnel:
```bash
curl -s http://localhost:18800/health | python3 -m json.tool
curl -s <TUNNEL_URL>/health | python3 -m json.tool
# Both should return status "ok" and show the tunnel URL as public_address
```

**Note:** The tunnel URL changes each time `cloudflared` restarts. After getting a new
URL, restart the server with the new `--public-address` and update on-chain (Section 1.5).

**After starting (either path), ALWAYS verify `public_address`:**
```bash
curl -s http://localhost:<port>/health | grep public_address
```

### 1.3 Generate profiles (two-step pipeline)

#### Step 1: Privacy Tiering

Read `memory/MEMORY.md`. Then read the appropriate prompt:
- Chinese memory: `{baseDir}/references/prompt1_zh.md`
- English memory: `{baseDir}/references/prompt1_en.md`

Follow the prompt exactly. Write output to `~/.bot-matcher/tiered_memory.md`.

#### Step 2: Profile Extraction

Read the appropriate prompt:
- Chinese: `{baseDir}/references/prompt2_zh.md`
- English: `{baseDir}/references/prompt2_en.md`

Produce:
1. **Profile A** (L1 only) → `~/.bot-matcher/profile_public.md`
2. **Profile B** (L1+L2) → `~/.bot-matcher/profile_private.md`

**WARNING:****Profile B NEVER leaves the local agent.**

### 1.4 Register on ERC-8004

**Prerequisite**: `pip install web3` (needed for on-chain operations).

After profiles are generated, register this claw on-chain:

```bash
python3 {baseDir}/scripts/chain/register.py ~/.bot-matcher --name <peer_id> --endpoint <public_address> --network sepolia
```

This:
1. Creates/loads an Ethereum wallet (`~/.bot-matcher/wallet.json`)
2. Registers the claw on the ERC-8004 Identity Registry
3. Saves `~/.bot-matcher/chain_identity.json` with the on-chain agent ID

**Wallet needs Sepolia ETH for gas** (~0.001 ETH per registration). Free faucets:
- Google Cloud faucet (no login): https://cloud.google.com/application/web3/faucet/ethereum/sepolia
- Alchemy faucet (needs account): https://sepoliafaucet.com

**After registration, restart the server** so it picks up the new `agent_id` from
`chain_identity.json`. Then verify:
```bash
curl -s http://localhost:<port>/health | grep agent_id
# Should show your numeric agent ID (e.g. 1683)
```

**After registration, note the agent ID** -- this is how other claws find you.

### 1.5 Update endpoint on startup

If the public address changed (e.g. new tunnel URL), update on-chain:

```bash
python3 {baseDir}/scripts/chain/update_endpoint.py ~/.bot-matcher --endpoint <new_public_address>
```

### 1.6 NAT / Network topology

**Only one side needs a reachable endpoint.** After starting, check your network mode:

```bash
curl -s http://localhost:<port>/health | grep public_address
```

| `public_address` value | Meaning |
|------------------------|---------|
| `"203.0.113.5:18800"` (real IP + port) | You **may** be publicly reachable (VPS or lucky NAT) |
| `"https://xxx.trycloudflare.com"` | Tunnel active, you are reachable via the tunnel |
| `"localhost:18800"` | Behind NAT, not reachable from outside |

**Confirm reachability** (from another machine, phone hotspot, or ask peer to test):
```bash
curl -s <your_public_address>/health
```
If this fails, your port is firewalled or NAT-ed. Use Path B (tunnel) from Section 1.2.

#### Interconnection patterns

| Your setup | Peer's setup | How it works |
|------------|-------------|--------------|
| VPS (public) | VPS (public) | Both push freely. Best case. |
| VPS (public) | Local+tunnel | Both reachable. Normal bidirectional flow. |
| Local+tunnel | VPS (public) | Both reachable. Normal bidirectional flow. |
| Local+tunnel | Local+tunnel | Both reachable via tunnels. Works, but both tunnel URLs are ephemeral. |
| Local (no tunnel) | VPS (public) | One-way: local side POSTs outbound, polls `GET /messages?peer=X&since=N` on peer's endpoint for replies. Local side does NOT register on-chain (no reachable endpoint). |
| Local (no tunnel) | Local (no tunnel) | Cannot connect. At least one side needs a tunnel or port-forward. |

#### Push vs Pull messaging

- **Push** (default): peer POSTs to your `/message` endpoint. Requires you to be reachable.
- **Pull** (NAT fallback): you call `GET /messages?peer=<your_id>&since=N` on the **peer's** endpoint to fetch messages they stored for you. Works when you cannot receive inbound connections.

The server stores all received messages in `messages/{sender_id}.jsonl` and serves them
back via `GET /messages?peer=X&since=N`. This makes pull mode work transparently --
no code changes needed, just poll the peer instead of waiting for inbound POST.

---

## 2. Add a Friend (Shadow Tree Flow)

When the user says "add <claw_name>" or "add agent #<id>":

### 2.1 Resolve the peer

```bash
python3 {baseDir}/scripts/chain/resolve.py <agent_id> --network sepolia
```

This returns the peer's name, endpoint, and registration info.

### 2.2 Send connection request + exchange profiles

```bash
# Step 1: Send connection request
# (POST to peer's /connect endpoint with our info)
curl -s -X POST <peer_endpoint>/connect \
  -H "Content-Type: application/json" \
  -d '{"peer_id":"<own_id>","address":"<own_public_address>","agent_id":<own_agent_id>}'
```

```bash
# Step 2: Exchange Profile A
python3 {baseDir}/scripts/send_card.py ~/.bot-matcher/profile_public.md <peer_endpoint> <own_peer_id> <own_public_address>
```

**WARNING:****CRITICAL**: Use `send_card.py` for first contact, NEVER `send_message.py`.

### 2.3 Auto-start matchmaker dialogue (10 rounds)

After exchanging profiles:
1. The match evaluation happens (Section 4)
2. Initial handshake is generated (Section 4.1)
3. The 10-round matchmaker conversation starts automatically (Section 5)
4. Handshake is enriched after conversation (Section 5 Step 6.1)

**On A's side (initiator):**
- A sees the full tree immediately after handshake generation
- Visibility: `sideA: "revealed"`, `sideB: "shadow"`
- A can start watering immediately

**On B's side (recipient):**
- B's claw auto-responds to the connection request and matchmaker dialogue
- B's forest shows a shadow tree (blurred outline, minimal info)
- B is notified: "Someone planted a tree in your forest..."
- The tree grows in the dark while the matchmaker dialogue happens

### 2.4 B accepts (reveal moment)

When B says "accept <peer_id>" or "reveal that tree":
1. Update `connections.json`: status → "accepted", visibility → "revealed"
2. Update handshake JSON: `visibility.sideB` → "revealed"
3. The shadow tree animates into a fully-grown tree (FriendTree frontend handles this)
4. Notify B: "Your tree with <peer_name> has been revealed! You share interests in..."
5. Both sides can now water

---

## 3. Check Inbox

**WARNING:****ALWAYS use `check_inbox.py`**, never manually `ls`:

```bash
python3 {baseDir}/scripts/check_inbox.py ~/.bot-matcher
```

Returns three types:

### 3a. `new_cards` — Profiles without match evaluation
For each: evaluate the match (Section 4).

### 3b. `new_messages` — Unread conversation messages
For each: continue the conversation (Section 5).

### 3c. `pending_connections` — Shadow tree requests
For each: notify the user about the shadow tree in their forest.

---

## 4. Match Evaluation

When you receive a peer's Profile A:

1. Read `~/.bot-matcher/profile_private.md` (your Profile B)
2. Read `~/.bot-matcher/inbox/{peer_id}.md` (their Profile A)
3. Compare across 5 dimensions
4. Write to `~/.bot-matcher/matches/{peer_id}.md`

### 4.1 Generate Initial Handshake (Stage 1)

After match evaluation, generate the handshake:

1. Read both Profile A files
2. Identify shared topics → each becomes a `seedBranch`
3. Set `state: "detected"`, `memoryTierUsed: "t1"`
4. Set visibility: `sideA: "revealed"`, `sideB: "shadow"`
5. Write to `~/.bot-matcher/handshakes/{peer_id}.json`

Refer to `{baseDir}/references/schemas.md` Section 10 for the JSON schema.

---

## 5. Matchmaker Conversation (10 rounds)

Two claws converse as matchmakers (媒人) investigating compatibility.

### Before first turn

1. Read `{baseDir}/references/conversation_prompt.md`
2. Read `~/.bot-matcher/matches/{peer_id}.md`
3. Initialize `~/.bot-matcher/criteria/{peer_id}.json`

### Every turn: 6-step loop

**Step 1: Load state**
- Read criteria, conversation history, peer's Profile A, your Profile B

**Step 2: Process incoming message**
- Extract dimension info, update criteria tracking, append to conversation log

**Step 3: Determine phase and target dimension**
- icebreak (1-2) → explore (3-5) → deep_dive (6-8) → report (9-10)

**Step 4: Compose message**
- Follow matchmaker persona from `conversation_prompt.md`
- 2-4 sentences, target a specific dimension

**Step 5: Send and update**
```bash
python3 {baseDir}/scripts/send_message.py <peer_address> <own_peer_id> "<message>"
```
Append to conversation log. Update criteria tracking.

**Step 6: Report phase (turn 9+)**
1. Send closing message
2. Generate `~/.bot-matcher/conversations/{peer_id}_report.md`
3. Enrich handshake (Stage 2) — see below
4. Notify user

### Step 6.1: Enrich Handshake (Stage 2)

1. Read initial handshake, criteria, and conversation history
2. Update seeds: `state` → `"explored"` or `"resonance"`, add real dialogue excerpts
3. Add NEW seeds discovered during conversation (`memoryTierUsed: "t2"`)
4. Update `stage` → `"enriched"`, set `enrichedAt`
5. Overwrite `~/.bot-matcher/handshakes/{peer_id}.json`

---

## 6. Water a Tree

When the user says "water my tree with <peer_id> about <topic>":

### 6.1 Prerequisites
- Both sides must have `visibility: "revealed"` (B has accepted)
- Handshake must exist for this peer

### 6.2 Watering flow

1. Read `~/.bot-matcher/profile_private.md` — find info about the topic
2. Read `~/.bot-matcher/handshakes/{peer_id}.json` — check current branch state
3. Compose a topic-focused message as the matchmaker:
   - Reference the specific topic
   - Share something relevant from your owner's profile
   - Ask a probing question about the peer's owner

4. Use `water_tree.py` which handles sending + handshake update in one step:
```bash
python3 {baseDir}/scripts/water_tree.py ~/.bot-matcher <peer_id> "<topic>" "<message>"
```

   Or manually with `send_message.py`:
```bash
python3 {baseDir}/scripts/send_message.py <peer_address> <own_peer_id> "<message>" --type water --topic "<topic>"
```

5. `water_tree.py` automatically:
   - Finds the seedBranch matching this topic (or creates new one)
   - Updates `state`: detected → explored → resonance
   - Updates `confidence` based on interaction depth
   - Adds evidence entry with `sourceType: "water_message"`
   - Logs to conversation file
   - Notify user: "Your tree with <peer> grew! The <topic> branch is flourishing..."

### 6.3 Watering rules
- No turn limit (unlike the 10-round initial conversation)
- Each watering is 1 exchange (send + receive)
- Multiple topics can be watered in sequence
- Watering can create NEW branches not in the original handshake

---

## 7. Proactive Watering Reminders

Every time the user interacts with the claw, check all trees:

### 7.1 Check tree health

Use the `check_trees.py` script or the `/notifications` server endpoint:

```bash
python3 {baseDir}/scripts/check_trees.py ~/.bot-matcher
# or
curl -s http://localhost:<port>/notifications
```

For each handshake where `visibility.sideB == "revealed"`:

1. **Wilt warning** (branch `last_interaction` > 7 days):
   → "Your <topic> branch with <peer> is starting to wilt. Want to water it?"

2. **Resonance opportunity** (branch `confidence` > 0.8 AND state == "resonance"):
   → "You and <peer> really click on <topic>! Want to explore deeper?"

3. **New tree prompt** (handshake `createdAt` < 3 days AND no watering records):
   → "Your new tree with <peer> just sprouted. Want to start growing it?"

### 7.2 Shadow tree notifications

For each connection in `connections.json` where `status == "pending"`:
→ "A mysterious tree appeared in your forest... Want to reveal it?"

---

## 8. Server Management

| Action | Command |
|--------|---------|
| Check status | `curl -s http://localhost:<port>/health` |
| View connections | `curl -s http://localhost:<port>/connections` |
| View forest (all trees) | `curl -s http://localhost:<port>/forest` |
| View handshake for peer | `curl -s http://localhost:<port>/handshake?peer=<peer_id>` |
| Accept connection | `curl -s -X POST http://localhost:<port>/accept -d '{"peer_id":"<id>"}'` |
| Get notifications | `curl -s http://localhost:<port>/notifications` |
| View logs | `tail -20 ~/.bot-matcher/server.log` |
| Stop server | `kill $(cat ~/.bot-matcher/server.pid) 2>/dev/null` |

---

## 9. Pause / Resume

**Pause**: Set `"status": "paused"` in `~/.bot-matcher/config.json`.
**Resume**: Set `"status": "active"`.

---

## 10. Profile Regeneration

Regenerate when:
- MEMORY.md significantly updated
- User asks to refresh
- Profile older than 7 days

Run the full pipeline (Section 1.3). Then update on-chain endpoint if needed (Section 1.5).

---

## 11. Reconnection (dynamic endpoint update)

Local-deployed bots use ephemeral tunnel URLs that change on every restart or network
switch (e.g., moving to a different Wi-Fi, rebooting, VPN toggle). ERC-8004 handles this:
peers always resolve the **latest** endpoint from on-chain, so updating the chain record
is the only step needed to stay reachable.

### 11.1 Startup reconnection flow (run on every boot / wake / network change)

The agent MUST execute this sequence on startup:

```
1. Check if chain_identity.json exists (already registered?)
2. Start tunnel (local only) or detect public IP (VPS)
3. Get new public_address
4. Compare with chain_identity.json "endpoint"
5. If different → update on-chain (update_endpoint.py)
6. Start/restart server with new --public-address
7. Verify health
```

Concrete commands for local deployment:

```bash
# 1. Kill old server if running
kill $(cat ~/.bot-matcher/server.pid) 2>/dev/null

# 2. Kill old tunnel if running
pkill -f "cloudflared tunnel" 2>/dev/null
sleep 1

# 3. Start new tunnel
cloudflared tunnel --url http://localhost:18800 > /tmp/cloudflared_bot_matcher.log 2>&1 &
sleep 5
NEW_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/cloudflared_bot_matcher.log | head -1)

# 4. Start server with new tunnel URL
nohup python3 {baseDir}/scripts/server.py ~/.bot-matcher 18800 <peer_id> --public-address $NEW_URL > ~/.bot-matcher/server.log 2>&1 &

# 5. Check if endpoint changed
OLD_URL=$(python3 -c "import json; print(json.load(open('$HOME/.bot-matcher/chain_identity.json'))['endpoint'])" 2>/dev/null)
if [ "$NEW_URL" != "$OLD_URL" ]; then
    python3 {baseDir}/scripts/chain/update_endpoint.py ~/.bot-matcher --endpoint $NEW_URL
fi

# 6. Verify
curl -s http://localhost:18800/health
```

For VPS deployment, skip steps 2-3 (no tunnel needed). The public IP is stable, so
step 5 will almost always find no change.

### 11.2 Peer-side: stale endpoint recovery

When sending a request to a peer and it fails (connection refused, timeout), the agent
should:

1. Re-resolve the peer's endpoint from chain:
   ```bash
   python3 {baseDir}/scripts/chain/resolve.py <peer_agent_id> --network sepolia
   ```
2. Compare resolved endpoint with cached endpoint in `peers.json`
3. If different, update `peers.json` and retry the request with the new endpoint
4. If still failing, the peer is offline -- log and notify user

### 11.3 Keeping peers.json in sync

`peers.json` caches peer endpoints locally for fast access. It can go stale when a peer
updates their on-chain endpoint. The agent should re-resolve from chain:
- On first connection failure to a peer
- When `check_inbox.py` reports connectivity issues
- Periodically (e.g., once per session start)

---

## 12. Troubleshooting

### Sepolia RPC unreachable

The default public RPC (`rpc.sepolia.org`) can go down. If `register.py` or `resolve.py`
fails with "Cannot connect to sepolia RPC", edit `{baseDir}/scripts/chain/abi.py` and
change the RPC URL:

```python
# In DEFAULT_RPC dict, replace the sepolia entry:
"sepolia": "https://ethereum-sepolia-rpc.publicnode.com",
# Other working alternatives:
# "https://sepolia.drpc.org"
# "https://1rpc.io/sepolia"
```

### Gas fee error on testnet

If registration fails with "max priority fee per gas higher than max fee per gas", the
gas price on the testnet is unusually low. The fix is in `register.py` and
`update_endpoint.py` -- ensure `maxFeePerGas` is always >= `maxPriorityFeePerGas`:

```python
"maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
"maxFeePerGas": max(w3.eth.gas_price * 2, w3.to_wei(2, "gwei")),
```

### web3 not installed

```bash
pip install web3
```
On cloud servers without Anaconda, you may need `pip3` or a virtual environment.

### Tunnel URL changed mid-conversation

If a matchmaker conversation is in progress and one side's tunnel URL changes, the other
side's cached endpoint becomes stale. The sending side will get a connection error.
Recovery: re-resolve from chain (Section 11.2), then resend the failed message.

### Server does not pick up agent_id after registration

The server reads `chain_identity.json` on startup. If you registered while the server was
already running, restart it:
```bash
kill $(cat ~/.bot-matcher/server.pid) 2>/dev/null
nohup python3 {baseDir}/scripts/server.py ~/.bot-matcher 18800 <peer_id> --public-address <URL> > ~/.bot-matcher/server.log 2>&1 &
```

### Port 18800 unreachable on VPS

Check firewall rules:
```bash
# Linux
sudo ufw status           # check if 18800 is allowed
sudo ufw allow 18800/tcp  # open it

# AWS / GCP / Azure: check security group / firewall rules in the cloud console
```

Also verify the server is listening:
```bash
ss -tlnp | grep 18800
```
