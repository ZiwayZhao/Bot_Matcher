#!/usr/bin/env python3
"""Check for new profiles, messages, and undiscovered gossip peers.

Usage:
  python3 check_inbox.py <data_dir>

Example:
  python3 check_inbox.py context-match

Output (stdout): JSON summary of:
  - new_cards: peers who sent Profile A but haven't been evaluated yet
  - new_messages: peers with unread conversation messages
  - new_peers: peers discovered via gossip but no card exchanged yet
"""

import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <data_dir>")
        sys.exit(1)

    data_dir = Path(sys.argv[1])
    inbox_dir = data_dir / "inbox"
    matches_dir = data_dir / "matches"
    messages_dir = data_dir / "messages"
    conversations_dir = data_dir / "conversations"
    peers_file = data_dir / "peers.json"

    # --- 1. New cards (in inbox but no match evaluation yet) ---
    new_cards = []
    inbox_peer_ids = set()
    if inbox_dir.exists():
        for card_file in sorted(inbox_dir.glob("*.md")):
            peer_id = card_file.stem
            inbox_peer_ids.add(peer_id)
            match_file = matches_dir / f"{peer_id}.md"
            if not match_file.exists():
                content = card_file.read_text(encoding="utf-8")
                preview = content[:200] + "..." if len(content) > 200 else content
                new_cards.append({
                    "peer_id": peer_id,
                    "file": str(card_file),
                    "preview": preview,
                })

    # --- 2. New messages (received but not yet in conversation log) ---
    new_messages = []
    if messages_dir.exists():
        for msg_file in sorted(messages_dir.glob("*.jsonl")):
            peer_id = msg_file.stem
            conv_file = conversations_dir / f"{peer_id}.jsonl"

            incoming_lines = msg_file.read_text(encoding="utf-8").strip().split("\n")
            incoming_count = len([l for l in incoming_lines if l.strip()])

            processed_count = 0
            if conv_file.exists():
                conv_lines = conv_file.read_text(encoding="utf-8").strip().split("\n")
                for line in conv_lines:
                    if line.strip():
                        try:
                            entry = json.loads(line)
                            if entry.get("role") == peer_id:
                                processed_count += 1
                        except json.JSONDecodeError:
                            pass

            unread = incoming_count - processed_count
            if unread > 0:
                latest = []
                for line in incoming_lines[processed_count:]:
                    if line.strip():
                        try:
                            latest.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
                new_messages.append({
                    "peer_id": peer_id,
                    "unread_count": unread,
                    "latest": latest[-3:],
                })

    # --- 3. New gossip peers (discovered but no card exchanged yet) ---
    new_peers = []
    if peers_file.exists():
        try:
            peers_data = json.loads(peers_file.read_text(encoding="utf-8"))
            for peer_id, info in peers_data.items():
                # Peer found via gossip but we haven't received their card yet
                if peer_id not in inbox_peer_ids:
                    new_peers.append({
                        "peer_id": peer_id,
                        "address": info.get("address", "unknown"),
                    })
        except (json.JSONDecodeError, KeyError):
            pass

    result = {
        "new_cards": new_cards,
        "new_cards_count": len(new_cards),
        "new_messages": new_messages,
        "new_messages_count": len(new_messages),
        "new_peers": new_peers,
        "new_peers_count": len(new_peers),
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
