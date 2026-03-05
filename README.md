# Bot-Matcher

An AI agent skill that discovers meaningful connections between people by exchanging privacy-tiered context profiles.

## How it works

```
memory.md → [Privacy Tiering] → [Profile Extraction] → Profile A (public) + Profile B (private)
                                                              ↓
                                                     Exchange via HTTP
                                                              ↓
                                                     Match Evaluation
                                                              ↓
                                                   Agent Conversation
```

1. **Privacy Tiering** — Every piece of information in the user's memory is classified into L1 (Public), L2 (Intimate), or L3 (Confessional)
2. **Profile Extraction** — Two profiles are generated:
   - **Profile A** (public): shared with other agents for initial screening
   - **Profile B** (private): never leaves the local agent, used for deep compatibility scoring
3. **Matching** — When agents exchange Profile A's, each evaluates compatibility using their own Profile B
4. **Conversation** — High-scoring matches trigger agent-to-agent conversation, with human oversight

## Install

Copy the skill directory into your nanobot/OpenClaw workspace:

```bash
cp -r skills/bot-matcher /path/to/your/workspace/skills/
```

## Quick Start

```
You: Set up bot-matcher as agent_alice on port 18800
Bot: [creates config, starts server, runs privacy tiering + profile extraction]

You: Connect to peer at localhost:18801
Bot: [sends Profile A, receives peer's, evaluates match]
Bot: 🤝 Found a connection! Score: 8/10. Starting conversation...

You: Show my conversation with agent_bob
Bot: [displays conversation log]

You: Stop conversation with agent_bob
Bot: [sends goodbye, stops messaging]
```

## Architecture

Self-contained skill with bundled HTTP server — no external dependencies, no centralized service.

- `scripts/server.py` — HTTP server (Python stdlib only)
- `scripts/send_card.py` — Send Profile A to a peer
- `scripts/send_message.py` — Send conversation message
- `scripts/check_inbox.py` — Check for new profiles and messages
- `references/prompt1_*.md` — Privacy Tiering prompts (EN/ZH)
- `references/prompt2_*.md` — Profile Extraction prompts (EN/ZH)

## Privacy

- Profile B **never** leaves the local agent
- L3 (Confessional) data is filtered out entirely
- All LLM processing runs on the user's own API key
- No centralized server — direct peer-to-peer HTTP
