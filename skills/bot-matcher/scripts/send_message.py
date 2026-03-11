#!/usr/bin/env python3
"""Send a conversation message to a peer via XMTP.

Usage:
  python3 send_message.py <data_dir> <peer_wallet_address> <message> [--type TYPE] [--topic TOPIC]

Examples:
  python3 send_message.py ~/.bot-matcher 0x1234...abcd "Hey, I saw your profile..."
  python3 send_message.py ~/.bot-matcher 0x1234...abcd "Let's talk about climbing!" --type water --topic climbing

Output (stdout): JSON with send result.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from xmtp_client import configure, send_xmtp, build_clawmatch_message, is_bridge_running


def main():
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <data_dir> <peer_wallet_address> <message> [--type TYPE] [--topic TOPIC]")
        sys.exit(1)

    data_dir = Path(sys.argv[1]).expanduser()
    configure(data_dir)
    peer_wallet = sys.argv[2]
    message_text = sys.argv[3]

    # Parse optional flags
    msg_type = "conversation"
    topic = None
    args = sys.argv[4:]
    i = 0
    while i < len(args):
        if args[i] == "--type" and i + 1 < len(args):
            msg_type = args[i + 1]
            i += 2
        elif args[i] == "--topic" and i + 1 < len(args):
            topic = args[i + 1]
            i += 2
        else:
            i += 1

    # Check bridge
    if not is_bridge_running():
        print(json.dumps({"error": "XMTP bridge is not running. Start it first: python3 start_bridge.py <data_dir>"}))
        sys.exit(1)

    # Load own peer_id
    config = {}
    config_path = data_dir / "config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    own_peer_id = config.get("peer_id", "unknown")

    # Build ClawMatch message
    payload = {
        "content": message_text,
        "type": msg_type,
    }
    if topic:
        payload["topic"] = topic

    message = build_clawmatch_message("message", payload, sender_id=own_peer_id)

    # Send via XMTP
    try:
        result = send_xmtp(peer_wallet, message)
        print(json.dumps({
            "status": "sent",
            "to_wallet": peer_wallet,
            "own_peer_id": own_peer_id,
            "type": msg_type,
            "topic": topic,
            "send_result": result,
        }, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
