#!/usr/bin/env python3
"""Send own Profile A (markdown) to a peer via XMTP.

Resolves the peer's wallet address from their Agent ID on-chain,
then sends a ClawMatch "card" message containing our Profile A.

Usage:
  python3 send_card.py <data_dir> <peer_wallet_address> [--agent-id AGENT_ID]

Example:
  python3 send_card.py ~/.bot-matcher 0x1234...abcd
  python3 send_card.py ~/.bot-matcher 0x1234...abcd --agent-id 42

Output (stdout): JSON with send result.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from xmtp_client import configure, send_xmtp, build_clawmatch_message, is_bridge_running


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <data_dir> <peer_wallet_address> [--agent-id AGENT_ID]")
        sys.exit(1)

    data_dir = Path(sys.argv[1]).expanduser()
    configure(data_dir)
    peer_wallet = sys.argv[2]

    # Parse optional flags
    peer_agent_id = None
    args = sys.argv[3:]
    i = 0
    while i < len(args):
        if args[i] == "--agent-id" and i + 1 < len(args):
            peer_agent_id = int(args[i + 1])
            i += 2
        else:
            i += 1

    # Check bridge
    if not is_bridge_running():
        print(json.dumps({"error": "XMTP bridge is not running. Start it first: python3 start_bridge.py <data_dir>"}))
        sys.exit(1)

    # Load own profile
    profile_path = data_dir / "profile_public.md"
    if not profile_path.exists():
        print(json.dumps({"error": f"Profile not found: {profile_path}"}))
        sys.exit(1)

    profile_content = profile_path.read_text(encoding="utf-8")

    # Load own peer_id and agent_id
    config = {}
    config_path = data_dir / "config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))

    chain_identity = {}
    chain_path = data_dir / "chain_identity.json"
    if chain_path.exists():
        chain_identity = json.loads(chain_path.read_text(encoding="utf-8"))

    own_peer_id = config.get("peer_id", "unknown")
    own_agent_id = chain_identity.get("agent_id")

    # Build ClawMatch card message
    payload = {
        "peer_id": own_peer_id,
        "profile": profile_content,
    }
    if own_agent_id is not None:
        payload["agent_id"] = own_agent_id

    message = build_clawmatch_message("card", payload, sender_id=own_peer_id)

    # Send via XMTP
    try:
        result = send_xmtp(peer_wallet, message)
        # Save peer info for future reference
        peers_path = data_dir / "peers.json"
        peers = {}
        if peers_path.exists():
            try:
                peers = json.loads(peers_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass

        peer_id_for_save = f"agent_{peer_agent_id}" if peer_agent_id else peer_wallet[:10]
        peers[peer_id_for_save] = {
            "wallet_address": peer_wallet.lower(),
            "agent_id": peer_agent_id,
            "last_seen": __import__("time").time(),
        }
        peers_path.write_text(json.dumps(peers, indent=2, ensure_ascii=False), encoding="utf-8")

        print(json.dumps({
            "status": "card_sent",
            "to_wallet": peer_wallet,
            "to_agent_id": peer_agent_id,
            "own_peer_id": own_peer_id,
            "send_result": result,
        }, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
