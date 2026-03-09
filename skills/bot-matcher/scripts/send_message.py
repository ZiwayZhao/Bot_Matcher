#!/usr/bin/env python3
"""Send a conversation message to a peer.

Usage:
  python3 send_message.py <peer_address> <sender_id> <message> [--type TYPE] [--topic TOPIC]

Examples:
  python3 send_message.py localhost:18800 agent_alice "Hey, I saw your profile..."
  python3 send_message.py localhost:18800 agent_alice "Let's talk about climbing!" --type water --topic climbing

Output (stdout): JSON with peer's response.
"""

import json
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError


def make_url(address: str, path: str) -> str:
    """Build a full URL from an address and path, supporting http/https prefixes."""
    if address.startswith("http://") or address.startswith("https://"):
        return f"{address.rstrip('/')}{path}"
    return f"http://{address}{path}"


def main():
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <peer_address> <sender_id> <message> [--type TYPE] [--topic TOPIC]")
        sys.exit(1)

    peer_address = sys.argv[1]
    sender_id = sys.argv[2]
    message = sys.argv[3]

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

    body = {
        "sender_id": sender_id,
        "content": message,
        "type": msg_type,
    }
    if topic:
        body["topic"] = topic

    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")

    url = make_url(peer_address, "/message")
    req = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            print(json.dumps(result, indent=2, ensure_ascii=False))
    except URLError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
