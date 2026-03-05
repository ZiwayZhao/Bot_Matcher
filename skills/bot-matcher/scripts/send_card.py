#!/usr/bin/env python3
"""Send own Profile A (markdown) to a peer and receive theirs back.

Usage:
  python3 send_card.py <profile_public.md> <peer_address> <own_peer_id>

Example:
  python3 send_card.py context-match/profile_public.md localhost:18800 agent_alice

Output (stdout): JSON with peer's response including their Profile A.
"""

import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError


def main():
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <profile_md_path> <peer_address> <own_peer_id>")
        sys.exit(1)

    profile_path = Path(sys.argv[1])
    peer_address = sys.argv[2]
    own_peer_id = sys.argv[3]

    if not profile_path.exists():
        print(json.dumps({"error": f"Profile not found: {profile_path}"}))
        sys.exit(1)

    profile_content = profile_path.read_text(encoding="utf-8")

    payload = json.dumps({
        "peer_id": own_peer_id,
        "profile": profile_content,
    }, ensure_ascii=False).encode("utf-8")

    url = f"http://{peer_address}/card"
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
