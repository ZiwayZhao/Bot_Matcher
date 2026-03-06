# Bot-Matcher Data Schemas

## Pipeline Overview

```
memory.md → [Prompt 1] → tiered_memory.md → [Prompt 2] → profile_public.md + profile_private.md
```

## 1. Tiered Memory (tiered_memory.md)

Output of Prompt 1. Human-readable summary of privacy classification.

```markdown
# Tiered Memory
> Source: memory/MEMORY.md
> Classified: {timestamp}
> Stats: L1={count} | L2={count} | L3={count} | meta={count}

## L1 — Public
| # | Content | Category |
|---|---------|----------|
| 1 | Works on open-source AI agent framework | professional |
| 2 | Interested in distributed systems | interests |

## L2 — Intimate
| # | Content | Category |
|---|---------|----------|
| 1 | Struggles with work-life balance | emotional_patterns |

## L3 — Confessional
(Items listed by count only. Content is NOT stored in this file.)
- {count} items classified as L3 (excluded from profile pipeline)

## Meta (excluded)
- {count} items classified as meta (system instructions, tool configs)
```

## 2. Profile A — Public (profile_public.md)

See `prompt2_en.md` or `prompt2_zh.md` for the full template.

Key sections: Demographics, Personality, Interests (deep/active/curious), Values, Conversation Style, Connection Signals.

**Rules:**
- Contains ONLY L1 data
- Shared freely with other agents via HTTP
- Must be informative enough for initial screening
- Must reveal nothing intimate

## 3. Profile B — Private (profile_private.md)

See `prompt2_en.md` or `prompt2_zh.md` for the full template.

Key sections: Emotional Landscape, Relationship Patterns, Growth Edges, Hidden Depths, Ideal Dynamic, Inferred Dealbreakers, Bridge Nodes, Adjacent Possible.

**Rules:**
- Contains L1 + L2 data
- NEVER leaves the local agent
- Used for compatibility scoring only
- `bridge_nodes` and `adjacent_possible` are the most critical fields for matching

## 4. Match Result (matches/{peer_id}.md)

```markdown
# Match: {peer_id}
> Evaluated: {timestamp}
> Score: {1-10}/10

## Common Ground
- {Specific shared area 1}
- {Specific shared area 2}
- {Specific shared area 3}

## Potential Value
{Why this match matters — what could emerge from this connection}

## Bridge Analysis
{How their bridge_nodes connect to the peer's interests, and vice versa}

## Suggested Opener
> {A natural conversation starter in the user's preferred language}

## Brief
{1-2 sentence executive summary for the human owner}
```

### Match Score Rubric

| Score | Level | Meaning |
|-------|-------|---------|
| 9-10 | Exceptional | Immediate deep connection potential, strongly aligned |
| 7-8 | Strong | Significant overlap, clear mutual benefit |
| 5-6 | Moderate | Some common ground, worth exploring |
| 3-4 | Weak | Tangential overlap, limited immediate value |
| 1-2 | Minimal | Little to no relevant connection |

## 5. Conversation Message (conversations/{peer_id}.jsonl)

Each line is a JSON object:

```json
{"role": "self", "content": "message text", "timestamp": "ISO 8601"}
{"role": "{peer_id}", "content": "reply text", "timestamp": "ISO 8601"}
```

## 6. Config (config.json)

```json
{
  "peer_id": "unique_name",
  "port": 18800,
  "peers": ["host:port", "host:port"],
  "status": "active",
  "language": "auto"
}
```

- `status`: `"active"` | `"paused"` — controls whether agent processes incoming cards/messages
- `language`: `"auto"` | `"en"` | `"zh"` — which prompt language to use (auto = detect from MEMORY.md)

## 7. HTTP Transport

### POST /card

Request:
```json
{
  "peer_id": "agent_alice",
  "profile": "# Profile: agent_alice\n> Generated: ...\n\n## Demographics\n..."
}
```

Response:
```json
{
  "status": "received",
  "card": {
    "peer_id": "agent_bob",
    "profile": "# Profile: agent_bob\n..."
  }
}
```

### POST /message

Request:
```json
{
  "sender_id": "agent_alice",
  "content": "Your suggested opener message here..."
}
```

Response:
```json
{"status": "received"}
```

### Address Format

Peer addresses support multiple formats:
- `host:port` — e.g. `localhost:18800`, `192.168.1.5:18800`
- `http://host:port` — explicit HTTP
- `https://host` — tunnel URLs like `https://abc123.trycloudflare.com`

All scripts auto-detect the protocol. Tunnel URLs (HTTPS) are fully supported for cross-internet connectivity.

---

## 8. Criteria Tracking (`criteria/{peer_id}.json`)

Persists the conversation exploration state per peer. Created when the first conversation starts, updated after every turn by the agent.

```json
{
  "peer_id": "agent_dl",
  "phase": "icebreak | explore | deep_dive | report | completed",
  "turn_count": 3,
  "dimensions": {
    "emotional_alignment": {"depth": 0, "notes": []},
    "intellectual_resonance": {"depth": 3, "notes": ["likes distributed systems", "building P2P framework", "gets excited about protocol design"]},
    "value_compatibility": {"depth": 1, "notes": ["values open source"]},
    "growth_potential": {"depth": 0, "notes": []},
    "communication_style_fit": {"depth": 2, "notes": ["formal but warm", "asks follow-up questions"]}
  },
  "last_probed_dimension": "intellectual_resonance",
  "topics_explored": ["distributed_systems", "open_source", "p2p"],
  "topics_to_explore": ["personal_growth", "conflict_resolution", "creative_interests"],
  "created_at": "2026-03-06T17:00:00Z",
  "updated_at": "2026-03-06T17:15:00Z"
}
```

**Depth scale**: 0 = unexplored, 1 = surface mention, 2 = one exchange, 3 = multiple data points, 4 = deep with examples, 5 = comprehensive.

**Dimensions**: emotional_alignment, intellectual_resonance, value_compatibility, growth_potential, communication_style_fit.

**Phase transitions**: icebreak (turns 1-2) → explore (3-5, any depth==0) → deep_dive (6-8) → report (9-10).

## 9. Conversation Report (`conversations/{peer_id}_report.md`)

Generated at the end of the matchmaker conversation (turn 9-10). Summarizes findings for the human owner.

```markdown
# Conversation Report: {peer_id}
> Turns: {turn_count}
> Phase: completed
> Generated: {timestamp}

## Dimension Assessment
| Dimension | Depth | Key Findings |
|-----------|-------|-------------|
| emotional_alignment | {depth}/5 | {notes summary} |
| intellectual_resonance | {depth}/5 | {notes summary} |
| value_compatibility | {depth}/5 | {notes summary} |
| growth_potential | {depth}/5 | {notes summary} |
| communication_style_fit | {depth}/5 | {notes summary} |

## Compatibility Signals
- {what looks promising — be specific}

## Tension Points
- {what might be problematic — be honest}

## Recommendation
{Should the humans meet? Why or why not? Be direct and useful.}
```
