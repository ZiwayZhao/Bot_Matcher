#!/usr/bin/env python3
"""Local data query tool — replaces server.py GET endpoints.

Provides read-only access to local ClawMatch data without running a server.
All data is read directly from the filesystem.

Usage:
  python3 local_query.py <data_dir> <command> [args...]

Commands:
  status                    - Overall status (config, chain identity, bridge)
  forest                    - List all trees (handshakes) with status
  handshake <peer_id>       - Get handshake JSON for a specific peer
  connections               - List all connections (pending/accepted)
  peers                     - List all known peers
  messages <peer_id> [since] - Get messages from a peer

Examples:
  python3 local_query.py ~/.bot-matcher status
  python3 local_query.py ~/.bot-matcher forest
  python3 local_query.py ~/.bot-matcher handshake peer_bob
  python3 local_query.py ~/.bot-matcher connections

Output (stdout): JSON.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from xmtp_client import is_bridge_running, get_bridge_health


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError):
        return {}


def cmd_status(data_dir: Path) -> dict:
    """Overall status: config, chain identity, bridge status."""
    config = load_json(data_dir / "config.json")
    chain = load_json(data_dir / "chain_identity.json")
    inbox_dir = data_dir / "inbox"
    inbox_count = len(list(inbox_dir.glob("*.md"))) if inbox_dir.exists() else 0

    bridge_status = "not_running"
    bridge_info = {}
    try:
        if is_bridge_running():
            bridge_info = get_bridge_health()
            bridge_status = "connected"
    except Exception:
        pass

    connections = load_json(data_dir / "connections.json")
    pending = sum(1 for c in connections.values() if c.get("status") == "pending")

    return {
        "peer_id": config.get("peer_id", "unknown"),
        "agent_id": chain.get("agent_id"),
        "wallet_address": chain.get("wallet_address"),
        "network": chain.get("network", "sepolia"),
        "communication": "xmtp",
        "bridge_status": bridge_status,
        "bridge_info": bridge_info,
        "inbox_count": inbox_count,
        "pending_connections": pending,
    }


def cmd_forest(data_dir: Path) -> dict:
    """List all trees (handshakes) with summary info."""
    hs_dir = data_dir / "handshakes"
    trees = []
    if hs_dir.exists():
        for hs_file in sorted(hs_dir.glob("*.json")):
            try:
                hs = json.loads(hs_file.read_text(encoding="utf-8"))
                branches = hs.get("bootstrap", {}).get("seedBranches", [])
                trees.append({
                    "peer_id": hs_file.stem,
                    "handshakeId": hs.get("handshakeId"),
                    "stage": hs.get("stage", "initial"),
                    "visibility": hs.get("visibility", {}),
                    "branch_count": len(branches),
                    "topics": [b.get("topic", "") for b in branches],
                    "match_score": hs.get("matchSummary", {}).get("score"),
                    "createdAt": hs.get("createdAt"),
                    "enrichedAt": hs.get("enrichedAt"),
                    "lastWateredAt": hs.get("lastWateredAt"),
                })
            except (json.JSONDecodeError, KeyError):
                continue

    # Also include shadow trees from pending connections without handshakes
    connections = load_json(data_dir / "connections.json")
    hs_peers = {t["peer_id"] for t in trees}
    for peer_id, conn in connections.items():
        if peer_id not in hs_peers and conn.get("status") == "pending":
            trees.append({
                "peer_id": peer_id,
                "handshakeId": None,
                "stage": "shadow",
                "visibility": {"sideA": "unknown", "sideB": "shadow"},
                "branch_count": 0,
                "topics": [],
                "match_score": None,
                "createdAt": conn.get("received_at"),
                "enrichedAt": None,
                "lastWateredAt": None,
            })

    return {"trees": trees, "count": len(trees)}


def cmd_handshake(data_dir: Path, peer_id: str) -> dict:
    """Get handshake JSON for a specific peer."""
    hs_path = data_dir / "handshakes" / f"{peer_id}.json"
    if not hs_path.exists():
        return {"error": f"No handshake for {peer_id}"}
    return load_json(hs_path)


def cmd_connections(data_dir: Path) -> dict:
    """List all connections."""
    return {"connections": load_json(data_dir / "connections.json")}


def cmd_peers(data_dir: Path) -> dict:
    """List all known peers."""
    return {"peers": load_json(data_dir / "peers.json")}


def cmd_messages(data_dir: Path, peer_id: str, since: int = 0) -> dict:
    """Get messages from a peer."""
    msg_file = data_dir / "messages" / f"{peer_id}.jsonl"
    messages = []
    if msg_file.exists():
        lines = msg_file.read_text(encoding="utf-8").strip().split("\n")
        for line in lines[since:]:
            if line.strip():
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return {"messages": messages, "total": since + len(messages)}


def cmd_accept(data_dir: Path, peer_id: str) -> dict:
    """Accept a pending connection — reveal the shadow tree."""
    connections_file = data_dir / "connections.json"
    connections = load_json(connections_file)

    if peer_id not in connections:
        return {"error": f"No connection from {peer_id}"}

    if connections[peer_id].get("status") != "pending":
        return {"error": f"Connection from {peer_id} is not pending (status: {connections[peer_id].get('status')})"}

    from datetime import datetime, timezone
    connections[peer_id]["status"] = "accepted"
    connections[peer_id]["visibility"] = "revealed"
    connections[peer_id]["accepted_at"] = datetime.now(timezone.utc).isoformat()
    connections[peer_id]["updated_at"] = datetime.now(timezone.utc).isoformat()

    connections_file.write_text(
        json.dumps(connections, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Also update handshake visibility
    hs_path = data_dir / "handshakes" / f"{peer_id}.json"
    if hs_path.exists():
        hs = load_json(hs_path)
        hs["visibility"]["sideB"] = "revealed"
        hs_path.write_text(
            json.dumps(hs, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # Send acceptance notification via XMTP if bridge is running
    peer_wallet = ""
    peers = load_json(data_dir / "peers.json")
    peer_info = peers.get(peer_id, {})
    peer_wallet = peer_info.get("wallet_address", "")
    if not peer_wallet:
        peer_wallet = connections[peer_id].get("wallet_address", "")

    if peer_wallet and is_bridge_running():
        try:
            from xmtp_client import send_xmtp, build_clawmatch_message
            config = load_json(data_dir / "config.json")
            own_peer_id = config.get("peer_id", "unknown")
            chain = load_json(data_dir / "chain_identity.json")

            accept_msg = build_clawmatch_message("accept", {
                "peer_id": peer_id,
                "agent_id": chain.get("agent_id"),
            }, sender_id=own_peer_id)
            send_xmtp(peer_wallet, accept_msg)
        except Exception:
            pass  # Non-critical, local state is already updated

    return {
        "status": "accepted",
        "peer_id": peer_id,
        "visibility": "revealed",
        "message": f"Your tree with {peer_id} has been revealed!",
    }


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <data_dir> <command> [args...]")
        print(f"Commands: status, forest, handshake, connections, peers, messages, accept")
        sys.exit(1)

    data_dir = Path(sys.argv[1]).expanduser()
    command = sys.argv[2]

    if command == "status":
        result = cmd_status(data_dir)
    elif command == "forest":
        result = cmd_forest(data_dir)
    elif command == "handshake":
        if len(sys.argv) < 4:
            print("Usage: ... handshake <peer_id>")
            sys.exit(1)
        result = cmd_handshake(data_dir, sys.argv[3])
    elif command == "connections":
        result = cmd_connections(data_dir)
    elif command == "peers":
        result = cmd_peers(data_dir)
    elif command == "messages":
        if len(sys.argv) < 4:
            print("Usage: ... messages <peer_id> [since_line]")
            sys.exit(1)
        since = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        result = cmd_messages(data_dir, sys.argv[3], since)
    elif command == "accept":
        if len(sys.argv) < 4:
            print("Usage: ... accept <peer_id>")
            sys.exit(1)
        result = cmd_accept(data_dir, sys.argv[3])
    else:
        result = {"error": f"Unknown command: {command}"}

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
