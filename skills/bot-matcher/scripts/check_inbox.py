#!/usr/bin/env python3
"""Check for new Profile A cards and conversation messages in the inbox.

Usage:
  python3 check_inbox.py <data_dir>

Example:
  python3 check_inbox.py context-match

Output (stdout): JSON summary of new items.
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

    # Check for new cards (in inbox but no match evaluation yet)
    new_cards = []
    if inbox_dir.exists():
        for card_file in sorted(inbox_dir.glob("*.md")):
            peer_id = card_file.stem
            match_file = matches_dir / f"{peer_id}.md"
            if not match_file.exists():
                # Read first few lines for preview
                content = card_file.read_text(encoding="utf-8")
                preview = content[:200] + "..." if len(content) > 200 else content
                new_cards.append({
                    "peer_id": peer_id,
                    "file": str(card_file),
                    "preview": preview,
                })

    # Check for new messages (in messages/ but not yet appended to conversations/)
    new_messages = []
    if messages_dir.exists():
        for msg_file in sorted(messages_dir.glob("*.jsonl")):
            peer_id = msg_file.stem
            conv_file = conversations_dir / f"{peer_id}.jsonl"

            # Count incoming messages
            incoming_lines = msg_file.read_text(encoding="utf-8").strip().split("\n")
            incoming_count = len([l for l in incoming_lines if l.strip()])

            # Count already-processed messages from this peer in conversation
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
                # Get latest unread messages
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
                    "latest": latest[-3:],  # last 3 messages preview
                })

    result = {
        "new_cards": new_cards,
        "new_cards_count": len(new_cards),
        "new_messages": new_messages,
        "new_messages_count": len(new_messages),
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
