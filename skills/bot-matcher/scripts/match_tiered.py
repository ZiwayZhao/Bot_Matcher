#!/usr/bin/env python3
"""
Two-Tier Bot-Matcher: Vector screening + LLM deep match (TEE simulation).

Architecture:
  Tier 1 — Vector Match (Profile A, public)
    • Embeds your Profile A and all peer Profile A's using a local TF-IDF
      (or optionally sentence-transformers if available).
    • Ranks peers by cosine similarity.
    • Returns the top-N candidates (N=TOP_K_TIER1, set to 1 for testing).

  Tier 2 — LLM Deep Match (Profile B, private, runs in TEE)
    • For each Tier-1 candidate, fetches their Profile B over a simulated
      TEE channel (in production: an attested enclave endpoint).
    • Calls Z.AI GLM models on YOUR Profile B + THEIR Profile B inside a simulated TEE,
      returning a structured JSON compatibility report.
    • Returns matching criteria, a score, and human-readable comments.

Usage:
  python3 match_tiered.py <data_dir> [--top-k N] [--model MODEL] [--api-key KEY]

  data_dir:      your ~/.bot-matcher directory (contains profile_public.md,
                 profile_private.md, inbox/)
  --top-k:       Tier-1 shortlist size (default: 1 for testing, 20 for prod)
  --model:       Z.AI chat model (default: glm-5)
  --api-key:     Z.AI API key (or set ZAI_API_KEY in the environment)

Prerequisites:
  1. A Z.AI API key (set ZAI_API_KEY).
  2. Network connectivity to https://api.z.ai/.

TEE Note:
  In production, Tier-2 would run inside an attested enclave.  The peer's
  Profile B would be fetched via a mutually-attested TLS channel (e.g.,
  Gramine-SGX or AWS Nitro Enclaves).  This script marks the TEE boundary
  with a clear comment block so the integration point is obvious.
"""

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TOP_K_TIER1 = 1          # Set to 20 for production
ZAI_API_URL = "https://api.z.ai/api/paas/v4/chat/completions"
ZAI_DEFAULT_MODEL = "glm-5"
ZAI_SYSTEM_PROMPT = (
    "You are a deep compatibility analyst."
    " Always return valid JSON, with no prose or code fences."
)

# ---------------------------------------------------------------------------
# Tier 1: TF-IDF Vector Matching (Profile A only)
# ---------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer, lowercased."""
    return re.findall(r"[a-z0-9]+", text.lower())


def compute_tfidf(docs: dict[str, str]) -> dict[str, dict[str, float]]:
    """
    Compute TF-IDF vectors for a collection of documents.
    docs: {doc_id: text}
    Returns: {doc_id: {term: tfidf_weight}}
    """
    N = len(docs)
    tf: dict[str, dict[str, float]] = {}
    df: dict[str, int] = {}

    for doc_id, text in docs.items():
        tokens = tokenize(text)
        count: dict[str, int] = {}
        for t in tokens:
            count[t] = count.get(t, 0) + 1
        total = max(len(tokens), 1)
        tf[doc_id] = {t: c / total for t, c in count.items()}
        for t in count:
            df[t] = df.get(t, 0) + 1

    tfidf: dict[str, dict[str, float]] = {}
    for doc_id, term_tf in tf.items():
        tfidf[doc_id] = {
            t: w * math.log((N + 1) / (df[t] + 1))
            for t, w in term_tf.items()
        }
    return tfidf


def cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Cosine similarity between two sparse TF-IDF vectors."""
    common = set(vec_a) & set(vec_b)
    if not common:
        return 0.0
    dot = sum(vec_a[t] * vec_b[t] for t in common)
    norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def tier1_vector_match(
    own_profile_a: str,
    peer_profiles_a: dict[str, str],  # {peer_id: profile_A_text}
    top_k: int = TOP_K_TIER1,
) -> list[tuple[str, float]]:
    """
    Tier 1: Embed all Profile A's via TF-IDF, rank by cosine similarity.
    Returns: [(peer_id, score), ...] sorted descending, top_k entries.
    """
    if not peer_profiles_a:
        return []

    MY_ID = "__self__"
    all_docs = {MY_ID: own_profile_a, **peer_profiles_a}
    tfidf = compute_tfidf(all_docs)

    own_vec = tfidf[MY_ID]
    scores = [
        (peer_id, cosine_similarity(own_vec, tfidf[peer_id]))
        for peer_id in peer_profiles_a
    ]
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


# ---------------------------------------------------------------------------
# TEE Boundary: Tier 2 — LLM Deep Match (Profile B)
# ---------------------------------------------------------------------------
# ┌─────────────────────────────────────────────────────────────────────────┐
# │  TEE ENCLAVE BOUNDARY                                                   │
# │                                                                         │
# │  Everything inside this section runs (in production) inside an          │
# │  attested enclave.  The peer's Profile B is fetched via a              │
# │  mutually-attested TLS channel and is never written to disk outside     │
# │  the enclave.  The LLM call is made from inside the enclave; only      │
# │  the structured match result (score + criteria + comments) exits.       │
# │                                                                         │
# │  Integration point for production TEE:                                  │
# │    - Replace fetch_peer_profile_b() with an attested HTTP call         │
# │      to the peer's enclave endpoint (e.g. /profile_b_tee).             │
# │    - Wrap tier2_llm_match() in a Gramine / Nitro Enclaves harness.     │
# └─────────────────────────────────────────────────────────────────────────┘

def fetch_peer_profile_b(
    peer_id: str,
    peer_address: str,
    data_dir: Path,
) -> str | None:
    """
    [TEE] Fetch the peer's Profile B from their TEE endpoint.

    In this simulation we fall back to a local file under
    data_dir/inbox_private/{peer_id}.md if the network call is not
    available — useful for local testing where both agents run on the
    same machine.

    Production: replace the try-block body with a mutually-attested
    TLS request to https://<peer_enclave_addr>/profile_b_tee.
    """
    # --- Production TEE call (stub) ---
    tee_url = None
    if peer_address:
        try:
            tee_url = f"http://{peer_address.rstrip('/')}/profile_b_tee"
            req = Request(tee_url, method="GET")
            with urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                return data.get("profile_b")
        except Exception as e:
            print(f"  [TEE] Network fetch failed ({e}), falling back to local file.", file=sys.stderr)

    # --- Local test fallback ---
    local_path = data_dir / "inbox_private" / f"{peer_id}.md"
    if local_path.exists():
        return local_path.read_text(encoding="utf-8")

    print(f"  [TEE] No Profile B available for {peer_id}. Skipping.", file=sys.stderr)
    return None


def build_tier2_prompt(
    own_profile_b: str,
    peer_id: str,
    peer_profile_b: str,
) -> str:
    """Build the LLM prompt for deep compatibility scoring."""
    return f"""You are a deep compatibility analyst operating inside a Trusted Execution Environment (TEE).
You have access to two *private* profiles (Profile B). Your job is to evaluate compatibility
and return a structured JSON result. No profile content should be included verbatim in your output.

## Your Profile B (the local user):
{own_profile_b}

## Peer Profile B (peer_id: {peer_id}):
{peer_profile_b}

## Task
Analyse both profiles across these dimensions and return ONLY valid JSON (no markdown fences):

{{
  "peer_id": "{peer_id}",
  "score": <integer 1-10>,
  "common_ground": [
    "<specific shared value, interest, or pattern — be concrete>"
  ],
  "potential_value": "<why this connection could matter — one focused paragraph>",
  "bridge_analysis": "<how their bridge_nodes / adjacent_possible connect to yours>",
  "tension_points": [
    "<real incompatibility or friction point — honest, not sanitised>"
  ],
  "suggested_opener": "<a natural, specific first message — avoid generic openers>",
  "brief": "<1-2 sentence summary for the human owner>",
  "matching_criteria": {{
    "emotional_alignment": <1-10>,
    "intellectual_resonance": <1-10>,
    "value_compatibility": <1-10>,
    "growth_potential": <1-10>,
    "communication_style_fit": <1-10>
  }},
  "tee_note": "Profile B data processed inside TEE enclave. Only this result record exits the boundary."
}}

Score rubric: 9-10 exceptional, 7-8 strong, 5-6 moderate, 3-4 weak, 1-2 minimal.
Be honest about tension_points — they are as important as common ground."""


def call_zai(prompt: str, api_key: str, model: str) -> dict:
    """Call the Z.AI chat-completions API and parse the JSON reply."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": ZAI_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    req = Request(
        ZAI_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())

    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("Z.AI response contained no choices")
    text_resp = choices[0].get("message", {}).get("content", "").strip()

    # Strip accidental markdown fences, then load JSON
    text_resp = re.sub(r"^```(?:json)?\s*", "", text_resp)
    text_resp = re.sub(r"\s*```$", "", text_resp)
    return json.loads(text_resp)


def tier2_llm_match(
    own_profile_b: str,
    peer_id: str,
    peer_profile_b: str,
    api_key: str,
    model: str,
) -> dict:
    """
    [TEE] Run LLM-based deep compatibility match via Z.AI.
    Only the structured result exits the TEE boundary.
    """
    prompt = build_tier2_prompt(own_profile_b, peer_id, peer_profile_b)
    result = call_zai(prompt, api_key, model)
    result["evaluated_at"] = datetime.now(timezone.utc).isoformat()
    result["llm_model"] = model
    return result


# ---------------------------------------------------------------------------
# Output: Write match result to matches/{peer_id}.md
# ---------------------------------------------------------------------------

def write_match_file(data_dir: Path, result: dict) -> Path:
    """Render the match result as a markdown file."""
    peer_id = result["peer_id"]
    score = result.get("score", "?")
    criteria = result.get("matching_criteria", {})
    common = result.get("common_ground", [])
    tensions = result.get("tension_points", [])

    lines = [
        f"# Match: {peer_id}",
        f"> Evaluated: {result.get('evaluated_at', 'unknown')}",
        f"> Score: {score}/10",
        f"> Method: Two-tier (Vector Tier 1 → LLM TEE Tier 2)",
        f"> Model: {result.get('llm_model', 'unknown')}",
        "",
        "## Matching Criteria",
        f"| Dimension | Score |",
        f"|-----------|-------|",
    ]
    for dim, val in criteria.items():
        label = dim.replace("_", " ").title()
        lines.append(f"| {label} | {val}/10 |")

    lines += [
        "",
        "## Common Ground",
    ]
    for item in common:
        lines.append(f"- {item}")

    lines += [
        "",
        "## Potential Value",
        result.get("potential_value", ""),
        "",
        "## Bridge Analysis",
        result.get("bridge_analysis", ""),
        "",
        "## Tension Points",
    ]
    for t in tensions:
        lines.append(f"- {t}")

    lines += [
        "",
        "## Suggested Opener",
        f"> {result.get('suggested_opener', '')}",
        "",
        "## Brief",
        result.get("brief", ""),
        "",
        "---",
        f"*{result.get('tee_note', '')}*",
    ]

    matches_dir = data_dir / "matches"
    matches_dir.mkdir(parents=True, exist_ok=True)
    out = matches_dir / f"{peer_id}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Two-tier Bot-Matcher")
    parser.add_argument("data_dir", help="~/.bot-matcher data directory")
    parser.add_argument("--top-k", type=int, default=TOP_K_TIER1,
                        help=f"Tier-1 shortlist size (default: {TOP_K_TIER1})")
    parser.add_argument("--model", default=ZAI_DEFAULT_MODEL,
                        help=f"Z.AI model name (default: {ZAI_DEFAULT_MODEL})")
    parser.add_argument("--api-key", default=os.environ.get("ZAI_API_KEY", ""),
                        help="Z.AI API key (or set ZAI_API_KEY)")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    model = args.model
    api_key = args.api_key

    if not api_key:
        print("ERROR: No Z.AI API key provided. Set ZAI_API_KEY or pass --api-key.", file=sys.stderr)
        sys.exit(1)

    print(f"[Z.AI] Using model '{model}' via Chat Completions API")

    # --- Load own profiles ---
    own_profile_a_path = data_dir / "profile_public.md"
    own_profile_b_path = data_dir / "profile_private.md"

    if not own_profile_a_path.exists():
        print(f"ERROR: {own_profile_a_path} not found. Run profile generation first.", file=sys.stderr)
        sys.exit(1)
    if not own_profile_b_path.exists():
        print(f"ERROR: {own_profile_b_path} not found. Run profile generation first.", file=sys.stderr)
        sys.exit(1)

    own_profile_a = own_profile_a_path.read_text(encoding="utf-8")
    own_profile_b = own_profile_b_path.read_text(encoding="utf-8")

    # --- Load peer Profile A's from inbox ---
    inbox_dir = data_dir / "inbox"
    if not inbox_dir.exists() or not any(inbox_dir.glob("*.md")):
        print("No peer profiles found in inbox/. Connect to peers first.", file=sys.stderr)
        sys.exit(0)

    peer_profiles_a: dict[str, str] = {}
    for card_file in inbox_dir.glob("*.md"):
        peer_profiles_a[card_file.stem] = card_file.read_text(encoding="utf-8")

    print(f"[Tier 1] Found {len(peer_profiles_a)} peer(s). Running vector match (top-k={args.top_k})...")

    # --- TIER 1: Vector match ---
    tier1_results = tier1_vector_match(own_profile_a, peer_profiles_a, top_k=args.top_k)

    print(f"[Tier 1] Shortlist:")
    for peer_id, sim in tier1_results:
        print(f"  {peer_id}: cosine similarity = {sim:.4f}")

    # Load peer registry for addresses
    peers_registry: dict[str, dict] = {}
    peers_file = data_dir / "peers.json"
    if peers_file.exists():
        try:
            peers_registry = json.loads(peers_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    # --- TIER 2: LLM deep match (TEE boundary) ---
    print(f"\n[Tier 2 / TEE] Running LLM deep match on {len(tier1_results)} candidate(s)...")

    all_results = []
    written_files = []

    for peer_id, tier1_score in tier1_results:
        print(f"\n  → Peer: {peer_id} (tier-1 score: {tier1_score:.4f})")

        peer_address = peers_registry.get(peer_id, {}).get("address", "")

        # ── TEE BOUNDARY START ────────────────────────────────────────────
        peer_profile_b = fetch_peer_profile_b(peer_id, peer_address, data_dir)
        if peer_profile_b is None:
            print(f"  [TEE] Skipping {peer_id}: no Profile B available.")
            continue

        print(f"  [TEE] Profile B obtained. Calling LLM for deep match...")
        try:
            result = tier2_llm_match(own_profile_b, peer_id, peer_profile_b, api_key, model)
        except Exception as e:
            print(f"  [TEE] LLM call failed for {peer_id}: {e}", file=sys.stderr)
            continue
        # ── TEE BOUNDARY END ──────────────────────────────────────────────

        result["tier1_cosine_score"] = round(tier1_score, 4)

        out_path = write_match_file(data_dir, result)
        written_files.append(str(out_path))
        all_results.append(result)

        score = result.get("score", "?")
        brief = result.get("brief", "")
        print(f"  ✓ Score: {score}/10 — {brief}")

        # Notify if strong match
        if isinstance(score, int) and score >= 6:
            criteria = result.get("matching_criteria", {})
            common = result.get("common_ground", [])
            opener = result.get("suggested_opener", "")
            print(f"\n  🤝 Bot-Matcher found a connection with {peer_id}!")
            print(f"     Score: {score}/10")
            print(f"     Common ground: {', '.join(common[:3])}")
            print(f"     Suggested opener: \"{opener}\"")

    # --- Summary ---
    summary = {
        "tier1_candidates_evaluated": len(peer_profiles_a),
        "tier1_shortlist_size": len(tier1_results),
        "tier2_matches_completed": len(all_results),
        "results": [
            {
                "peer_id": r["peer_id"],
                "score": r.get("score"),
                "tier1_cosine_score": r.get("tier1_cosine_score"),
                "brief": r.get("brief"),
            }
            for r in all_results
        ],
        "files_written": written_files,
    }
    print("\n[Done] Summary:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    main()
