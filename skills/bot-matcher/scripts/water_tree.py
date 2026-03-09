#!/usr/bin/env python3
"""Water a tree branch — send a topic-focused message and update handshake.

Handles the full watering flow:
1. Check prerequisites (both sides revealed)
2. Read handshake, find or create relevant seedBranch
3. Send the water message via send_message.py
4. Update handshake with new evidence and state

Usage:
  python3 water_tree.py <data_dir> <peer_id> <topic> <message>

Example:
  python3 water_tree.py ~/.bot-matcher peer_bob "distributed systems" "Let's dig into P2P protocols!"

Output (stdout): JSON with updated branch info.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError


def make_url(address: str, path: str) -> str:
    if address.startswith("http://") or address.startswith("https://"):
        return f"{address.rstrip('/')}{path}"
    return f"http://{address}{path}"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def check_prerequisites(data_dir: Path, peer_id: str) -> tuple[bool, str]:
    """Check that both sides have visibility: revealed."""
    handshake_path = data_dir / "handshakes" / f"{peer_id}.json"
    if not handshake_path.exists():
        return False, f"No handshake found for {peer_id}"

    handshake = load_json(handshake_path)
    vis = handshake.get("visibility", {})

    if vis.get("sideA") != "revealed":
        return False, "Side A visibility is not 'revealed'"
    if vis.get("sideB") != "revealed":
        return False, f"Side B visibility is '{vis.get('sideB', 'unknown')}'. Peer must accept the connection first."

    return True, "ok"


def find_or_create_branch(handshake: dict, topic: str) -> tuple[dict, bool]:
    """Find an existing seedBranch matching the topic, or create a new one.
    Returns (branch, is_new)."""
    branches = handshake.get("bootstrap", {}).get("seedBranches", [])

    # Try exact match first, then substring match
    for branch in branches:
        if branch.get("topic", "").lower() == topic.lower():
            return branch, False
    for branch in branches:
        if topic.lower() in branch.get("topic", "").lower() or branch.get("topic", "").lower() in topic.lower():
            return branch, False

    # Create new branch
    new_branch = {
        "seedId": f"seed_{len(branches) + 1}",
        "topic": topic,
        "parentSeedId": None,
        "state": "detected",
        "initiatedBy": "self",
        "memoryTierUsed": "t2",
        "matchDimension": None,
        "summaryA": f"Watering conversation about {topic}",
        "summaryB": None,
        "dialogueSeed": [],
        "evidence": [],
        "confidence": 0.3,
    }
    return new_branch, True


def update_branch_after_water(branch: dict, own_peer_id: str, message: str, response_content: str | None = None):
    """Update a branch after a watering exchange."""
    now = datetime.now(timezone.utc).isoformat()

    # Update state: detected → explored → resonance
    current_state = branch.get("state", "detected")
    if current_state == "detected":
        branch["state"] = "explored"
    elif current_state == "explored" and response_content:
        # Only upgrade to resonance if we got a substantive response
        if len(response_content) > 20:
            branch["state"] = "resonance"

    # Add evidence
    evidence = branch.get("evidence", [])
    evidence.append({
        "sourceType": "water_message",
        "sourceRefId": f"water_{own_peer_id}_{int(time.time())}",
        "occurredAt": now,
    })
    branch["evidence"] = evidence

    # Update confidence based on interaction count
    water_count = sum(1 for e in evidence if e.get("sourceType") == "water_message")
    branch["confidence"] = min(1.0, 0.3 + water_count * 0.15)

    # Update dialogue seed with real exchange
    ds = branch.get("dialogueSeed", [])
    ds.append({"speaker": own_peer_id, "text": message[:200]})
    if response_content:
        ds.append({"speaker": "peer", "text": response_content[:200]})
    # Keep last 6 exchanges
    branch["dialogueSeed"] = ds[-6:]

    # Track last interaction time
    branch["last_interaction"] = now

    return branch


def send_water_message(peer_address: str, sender_id: str, message: str, topic: str) -> dict:
    """Send a water message to the peer."""
    body = {
        "sender_id": sender_id,
        "content": message,
        "type": "water",
        "topic": topic,
    }
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    url = make_url(peer_address, "/message")
    req = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def water_tree(data_dir: Path, peer_id: str, topic: str, message: str) -> dict:
    """Execute the full watering flow."""
    data_dir = data_dir.expanduser()

    # 1. Check prerequisites
    ok, reason = check_prerequisites(data_dir, peer_id)
    if not ok:
        return {"error": reason, "watered": False}

    # 2. Load handshake
    handshake_path = data_dir / "handshakes" / f"{peer_id}.json"
    handshake = load_json(handshake_path)

    # 3. Find or create branch
    branch, is_new = find_or_create_branch(handshake, topic)

    # 4. Get peer address
    peers_path = data_dir / "peers.json"
    peers = load_json(peers_path)
    peer_info = peers.get(peer_id, {})
    peer_address = peer_info.get("address", "")

    if not peer_address:
        # Try connections.json
        conns = load_json(data_dir / "connections.json")
        conn = conns.get(peer_id, {})
        peer_address = conn.get("address", "")

    if not peer_address:
        return {"error": f"No address found for peer {peer_id}", "watered": False}

    # 5. Load config for own peer_id
    config = load_json(data_dir / "config.json")
    own_peer_id = config.get("peer_id", "unknown")

    # 6. Send water message
    try:
        result = send_water_message(peer_address, own_peer_id, message, topic)
    except URLError as e:
        return {"error": f"Failed to send: {e}", "watered": False}

    # 7. Update branch
    branch = update_branch_after_water(branch, own_peer_id, message)

    # 8. Write back to handshake
    if is_new:
        if "bootstrap" not in handshake:
            handshake["bootstrap"] = {"mode": "seeded", "source": "conversation", "seedBranches": []}
        handshake["bootstrap"]["seedBranches"].append(branch)
    else:
        # Update in place
        branches = handshake["bootstrap"]["seedBranches"]
        for i, b in enumerate(branches):
            if b.get("seedId") == branch.get("seedId"):
                branches[i] = branch
                break

    handshake["lastWateredAt"] = datetime.now(timezone.utc).isoformat()
    save_json(handshake_path, handshake)

    # 9. Also log to conversation file
    conv_dir = data_dir / "conversations"
    conv_dir.mkdir(exist_ok=True)
    conv_file = conv_dir / f"{peer_id}.jsonl"
    entry = {
        "role": "self",
        "content": message,
        "type": "water",
        "topic": topic,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(conv_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return {
        "watered": True,
        "peer_id": peer_id,
        "topic": topic,
        "branch_state": branch["state"],
        "branch_confidence": branch["confidence"],
        "is_new_branch": is_new,
        "send_result": result,
    }


def main():
    if len(sys.argv) < 5:
        print(f"Usage: {sys.argv[0]} <data_dir> <peer_id> <topic> <message>")
        print(f"Example: {sys.argv[0]} ~/.bot-matcher peer_bob 'climbing' 'Tell me about your climbing!'")
        sys.exit(1)

    data_dir = Path(sys.argv[1])
    peer_id = sys.argv[2]
    topic = sys.argv[3]
    message = sys.argv[4]

    result = water_tree(data_dir, peer_id, topic, message)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result.get("watered"):
        sys.exit(1)


if __name__ == "__main__":
    main()
